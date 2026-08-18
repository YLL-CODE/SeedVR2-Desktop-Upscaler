from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from .pipeline import tile_plan


def create_artifacts(image_path: Path, report_path: Path) -> tuple[Path, Path]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    preview_path = image_path.with_name(f"{image_path.stem}-preview.png")
    seams_path = image_path.with_name(f"{image_path.stem}-seams.png")
    with Image.open(image_path) as opened:
        image = opened.convert("RGB")
        preview = image.copy()
        preview.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
        preview.save(preview_path)

        plan = tile_plan(image.width, image.height)
        crop_width, crop_height, label_height = 768, 512, 32
        crops: list[tuple[str, Image.Image]] = []
        for column in range(1, plan["columns"]):
            current = plan["positions"][column]
            overlap = plan["tileWidth"] - current["left"]
            x = current["left"] + overlap // 2
            box = (x - crop_width // 2, image.height // 2 - crop_height // 2, x + crop_width // 2, image.height // 2 + crop_height // 2)
            crops.append((f"Vertical seam {column}", image.crop(box)))
        for row in range(1, plan["rows"]):
            current = plan["positions"][row * plan["columns"]]
            overlap = plan["tileHeight"] - current["top"]
            y = current["top"] + overlap // 2
            box = (image.width // 2 - crop_width // 2, y - crop_height // 2, image.width // 2 + crop_width // 2, y + crop_height // 2)
            crops.append((f"Horizontal seam {row}", image.crop(box)))

        sheet = Image.new("RGB", (crop_width * 2, (crop_height + label_height) * 2), "#202020")
        draw = ImageDraw.Draw(sheet)
        for index, (label, crop) in enumerate(crops):
            x = (index % 2) * crop_width
            y = (index // 2) * (crop_height + label_height)
            sheet.paste(ImageOps.fit(crop, (crop_width, crop_height), Image.Resampling.LANCZOS), (x, y + label_height))
            draw.text((x + 10, y + 8), label, fill="white")
        sheet.save(seams_path)

    report["artifacts"] = {"preview": str(preview_path), "seams": str(seams_path)}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return preview_path, seams_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    preview, seams = create_artifacts(args.image, args.report)
    print(preview)
    print(seams)


if __name__ == "__main__":
    main()
