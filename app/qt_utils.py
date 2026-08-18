from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from .i18n import tr


PREVIEW_MAX_SIZE = (1200, 900)
SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})


def format_duration(seconds: float) -> str:
    total = max(0, round(float(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def load_preview_image(path: Path) -> tuple[Image.Image, tuple[int, int]]:
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened)
        original_size = image.size
        image.thumbnail(PREVIEW_MAX_SIZE, Image.Resampling.LANCZOS)
        if "A" in image.getbands() or "transparency" in image.info:
            rgba = image.convert("RGBA")
            flattened = Image.new("RGB", rgba.size, "#343733")
            flattened.paste(rgba, mask=rgba.getchannel("A"))
            image = flattened
        else:
            image = image.convert("RGB")
        return image.copy(), original_size


def file_details(path: Path, dimensions: tuple[int, int]) -> str:
    size = path.stat().st_size
    size_text = f"{size / 1048576:.1f} MB" if size >= 1048576 else f"{max(1, round(size / 1024))} KB"
    file_type = path.suffix.removeprefix(".").upper() or tr("input.image_type")
    return f"{dimensions[0]} × {dimensions[1]}  ·  {file_type}  ·  {size_text}"


def compact_filename(name: str) -> str:
    return name if len(name) <= 24 else f"{name[:20]}…{Path(name).suffix}"


def validate_input_image_paths(paths: list[str] | tuple[str, ...]) -> tuple[Path | None, str]:
    if len(paths) != 1:
        return None, tr("input.only_one")
    source = Path(paths[0])
    if not source.is_file():
        return None, tr("input.not_found")
    if source.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        return None, tr("input.unsupported")
    return source, ""
