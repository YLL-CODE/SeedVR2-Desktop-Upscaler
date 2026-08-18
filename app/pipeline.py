from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageOps

from .config import BLEND_PADDING, SCALE, SUPPORTED_GRIDS, SUPPORTED_SCALES, memory_profile
from .i18n import tr

Progress = Callable[[str, int, int], None]


def automatic_grid(width: int, height: int, vram_bytes: int) -> tuple[int, int]:
    limit = int(memory_profile(vram_bytes)["tileInput"])
    return max(3, math.ceil(width / (limit * 0.9))), max(3, math.ceil(height / (limit * 0.9)))


def tile_plan(width: int, height: int, grid_columns: int = 3, grid_rows: int | None = None) -> dict[str, Any]:
    grid_rows = grid_columns if grid_rows is None else grid_rows
    tile_width = int(width / (grid_columns * 0.9) / 8) * 8
    tile_height = int(height / (grid_rows * 0.9) / 8) * 8
    if tile_width < 8 or tile_height < 8:
        raise ValueError(tr("error.image_too_small"))

    def axis(size: int, tile_size: int) -> tuple[int, int, int]:
        count = int(np.ceil(size / tile_size))
        overlap = (count * tile_size - size) // (count - 1)
        return count, overlap, tile_size - overlap

    columns, _, x_step = axis(width, tile_width)
    rows, _, y_step = axis(height, tile_height)
    positions = []
    for row in range(rows):
        for column in range(columns):
            left = min(column * x_step, width - tile_width)
            top = min(row * y_step, height - tile_height)
            positions.append({"left": left, "top": top, "width": tile_width, "height": tile_height})
    return {
        "tileWidth": tile_width,
        "tileHeight": tile_height,
        "columns": columns,
        "rows": rows,
        "positions": positions,
    }


def prepare(
    source_path: Path,
    staging: Path,
    progress: Progress | None = None,
    *,
    scale: int = SCALE,
    grid_size: int | None = 3,
    vram_bytes: int = 0,
) -> dict[str, Any]:
    if scale not in SUPPORTED_SCALES:
        raise ValueError(tr("error.scale_unsupported", scale=scale))
    if grid_size is not None and grid_size not in SUPPORTED_GRIDS:
        raise ValueError(tr("error.grid_unsupported", grid=grid_size))
    input_dir = staging / "input"
    processed_dir = staging / "processed"
    input_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as opened:
        image = ImageOps.exif_transpose(opened)
        source_width, source_height = image.size
        target_size = (source_width * scale, source_height * scale)
        rgba = image.convert("RGBA")
        has_alpha = "A" in image.getbands() or "transparency" in image.info
        target_rgb = rgba.convert("RGB").resize(target_size, Image.Resampling.LANCZOS)
        if has_alpha:
            rgba.getchannel("A").resize(target_size, Image.Resampling.LANCZOS).save(staging / "alpha.png")

    grid_columns, grid_rows = (
        automatic_grid(source_width, source_height, vram_bytes)
        if grid_size is None
        else (grid_size, grid_size)
    )
    plan = tile_plan(*target_size, grid_columns, grid_rows)
    total = len(plan["positions"])
    for index, position in enumerate(plan["positions"]):
        box = (
            position["left"],
            position["top"],
            position["left"] + position["width"],
            position["top"] + position["height"],
        )
        size = (round(position["width"] / scale), round(position["height"] / scale))
        target_rgb.crop(box).resize(size, Image.Resampling.LANCZOS).save(input_dir / f"{index:03d}.png")
        if progress:
            progress("prepare", index + 1, total)

    manifest = {
        "sourceWidth": source_width,
        "sourceHeight": source_height,
        "targetWidth": target_size[0],
        "targetHeight": target_size[1],
        "scale": scale,
        "gridPreset": "auto" if grid_size is None else f"{grid_size}x{grid_size}",
        "seedInputWidth": round(plan["tileWidth"] / scale),
        "seedInputHeight": round(plan["tileHeight"] / scale),
        "memoryProfile": memory_profile(vram_bytes)["label"],
        "hasAlpha": has_alpha,
        **plan,
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _read_tile(path: Path, width: int, height: int) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(
            image.convert("RGB").resize((width, height), Image.Resampling.LANCZOS), dtype=np.uint8
        )


def _blend_horizontal(left: np.ndarray, right: np.ndarray, overlap: int, padding: int) -> np.ndarray:
    blend = min(overlap, padding)
    offset = (overlap - blend) // 2
    seam_start = left.shape[1] - overlap + offset
    right_start = left.shape[1] - offset
    steps = right_start - seam_start
    alpha = (1.0 - np.arange(steps, dtype=np.float32) / blend)[None, :, None]
    mixed = np.rint(left[:, seam_start:right_start] * alpha + right[:, offset : offset + steps] * (1 - alpha))
    return np.concatenate((left[:, :seam_start], mixed.astype(np.uint8), right[:, offset + steps :]), axis=1)


def _blend_vertical(top: np.ndarray, bottom: np.ndarray, overlap: int, padding: int) -> np.ndarray:
    blend = min(overlap, padding)
    offset = (overlap - blend) // 2
    seam_start = top.shape[0] - overlap + offset
    bottom_start = top.shape[0] - offset
    steps = bottom_start - seam_start
    alpha = (1.0 - np.arange(steps, dtype=np.float32) / blend)[:, None, None]
    mixed = np.rint(top[seam_start:bottom_start] * alpha + bottom[offset : offset + steps] * (1 - alpha))
    return np.concatenate((top[:seam_start], mixed.astype(np.uint8), bottom[offset + steps :]), axis=0)


def assemble(staging: Path, output_path: Path, padding: int = BLEND_PADDING) -> dict[str, Any]:
    manifest = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
    tiles = [
        _read_tile(staging / "processed" / f"{index:03d}.png", manifest["tileWidth"], manifest["tileHeight"])
        for index in range(len(manifest["positions"]))
    ]
    rows = []
    for row in range(manifest["rows"]):
        image = tiles[row * manifest["columns"]]
        for column in range(1, manifest["columns"]):
            index = row * manifest["columns"] + column
            previous = manifest["positions"][index - 1]
            current = manifest["positions"][index]
            overlap = previous["left"] + manifest["tileWidth"] - current["left"]
            image = _blend_horizontal(image, tiles[index], overlap, padding)
        rows.append(image)
    image = rows[0]
    for row in range(1, len(rows)):
        previous = manifest["positions"][(row - 1) * manifest["columns"]]
        current = manifest["positions"][row * manifest["columns"]]
        overlap = previous["top"] + manifest["tileHeight"] - current["top"]
        image = _blend_vertical(image, rows[row], overlap, padding)
    expected = (manifest["targetHeight"], manifest["targetWidth"])
    if image.shape[:2] != expected:
        raise RuntimeError(
            tr(
                "error.assembled_size",
                actual_width=image.shape[1],
                actual_height=image.shape[0],
                expected_width=expected[1],
                expected_height=expected[0],
            )
        )

    result = Image.fromarray(image)
    if manifest["hasAlpha"] and (staging / "alpha.png").exists():
        with Image.open(staging / "alpha.png") as alpha:
            result.putalpha(alpha.convert("L"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.parent / f".{output_path.stem}-{os.getpid()}.tmp.png"
    result.save(temporary, format="PNG")
    os.replace(temporary, output_path)
    return {"width": result.width, "height": result.height, "output": str(output_path)}


def unique_output_path(source: Path, output_dir: Path, scale: int = SCALE) -> Path:
    if scale not in SUPPORTED_SCALES:
        raise ValueError(tr("error.scale_unsupported", scale=scale))
    base = output_dir / f"{source.stem}-seedvr2-{scale}x.png"
    if _output_pair_available(base):
        return base
    for index in range(2, 10_000):
        candidate = output_dir / f"{source.stem}-seedvr2-{scale}x-{index}.png"
        if _output_pair_available(candidate):
            return candidate
    raise RuntimeError(tr("error.output_names"))


def _output_pair_available(candidate: Path) -> bool:
    lock = candidate.with_suffix(candidate.suffix + ".lock")
    return not candidate.exists() and not candidate.with_suffix(".json").exists() and not lock.exists()


def reserve_output_path(source: Path, output_dir: Path, scale: int = SCALE) -> tuple[Path, Path]:
    for _ in range(10_000):
        candidate = unique_output_path(source, output_dir, scale)
        lock = candidate.with_suffix(candidate.suffix + ".lock")
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        os.close(descriptor)
        if not candidate.exists() and not candidate.with_suffix(".json").exists():
            return candidate, lock
        lock.unlink(missing_ok=True)
    raise RuntimeError(tr("error.output_reserve"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def seam_metric(path: Path, manifest: dict[str, Any]) -> dict[str, float]:
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("RGB"), dtype=np.int16)
    scores = []
    for column in range(1, manifest["columns"]):
        position = manifest["positions"][column]
        overlap = manifest["tileWidth"] - position["left"]
        x = position["left"] + overlap // 2
        scores.append(float(np.abs(pixels[:, x] - pixels[:, x - 1]).mean()))
    for row in range(1, manifest["rows"]):
        position = manifest["positions"][row * manifest["columns"]]
        overlap = manifest["tileHeight"] - position["top"]
        y = position["top"] + overlap // 2
        scores.append(float(np.abs(pixels[y] - pixels[y - 1]).mean()))
    return {"maxMeanAdjacentChange": max(scores, default=0.0), "normalized": max(scores, default=0.0) / 255.0}


def copy_source_to_ascii(source: Path, staging: Path) -> Path:
    suffix = source.suffix.lower() if source.suffix else ".png"
    target = staging / f"source{suffix}"
    shutil.copy2(source, target)
    return target
