from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.config import memory_profile
from app.i18n import LANG_ZH, get_language, set_language
from app.pipeline import automatic_grid, assemble, prepare, reserve_output_path, tile_plan, unique_output_path


class PipelineTests(unittest.TestCase):
    def test_memory_profiles_cover_supported_vram_range(self) -> None:
        self.assertEqual(memory_profile(8 * 1024**3)["label"], "8GB")
        self.assertEqual(memory_profile(12 * 1024**3)["label"], "12GB")
        self.assertEqual(memory_profile(16 * 1024**3)["label"], "16GB")
        self.assertTrue(memory_profile(8 * 1024**3)["swapIo"])

    def test_verified_tile_geometry(self) -> None:
        plan = tile_plan(8192, 6144)
        self.assertEqual((plan["columns"], plan["rows"]), (3, 3))
        self.assertEqual((plan["tileWidth"], plan["tileHeight"]), (3032, 2272))
        self.assertEqual((plan["tileWidth"] // 4, plan["tileHeight"] // 4), (758, 568))

    def test_auto_grid_adapts_to_8_to_16_gb(self) -> None:
        gib = 1024**3
        self.assertEqual(automatic_grid(3840, 2160, 16 * gib), (5, 3))
        self.assertEqual(automatic_grid(3840, 2160, 12 * gib), (6, 4))
        self.assertEqual(automatic_grid(3840, 2160, 8 * gib), (9, 5))

    def test_prepare_and_assemble_round_trip_with_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "中文输入.png"
            image = Image.new("RGBA", (96, 72), (30, 80, 160, 190))
            image.save(source)
            staging = root / "ascii-task"
            manifest = prepare(source, staging)
            self.assertTrue(manifest["hasAlpha"])
            self.assertEqual((manifest["columns"], manifest["rows"]), (3, 3))
            for tile in (staging / "input").glob("*.png"):
                shutil.copy2(tile, staging / "processed" / tile.name)
            output = root / "结果.png"
            result = assemble(staging, output)
            self.assertEqual((result["width"], result["height"]), (384, 288))
            with Image.open(output) as final:
                self.assertEqual(final.mode, "RGBA")
                self.assertEqual(final.size, (384, 288))

    def test_unique_output_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.png"
            source.touch()
            first = unique_output_path(source, root)
            self.assertEqual(first.name, "input-seedvr2-4x.png")
            first.touch()
            self.assertEqual(unique_output_path(source, root).name, "input-seedvr2-4x-2.png")
            self.assertEqual(unique_output_path(source, root, 8).name, "input-seedvr2-8x.png")

    def test_unique_output_preserves_orphan_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.png"
            source.touch()
            (root / "input-seedvr2-4x.json").write_text("old", encoding="utf-8")
            self.assertEqual(unique_output_path(source, root).name, "input-seedvr2-4x-2.png")

    def test_output_reservation_prevents_cross_process_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.png"
            source.touch()
            first, first_lock = reserve_output_path(source, root)
            second, second_lock = reserve_output_path(source, root)
            try:
                self.assertNotEqual(first, second)
            finally:
                first_lock.unlink()
                second_lock.unlink()

    def test_manifest_is_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            Image.new("RGB", (80, 64), "navy").save(source)
            prepare(source, root / "task")
            data = json.loads((root / "task" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(data["targetWidth"], 320)

    def test_scale_and_manual_grid_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            Image.new("RGB", (96, 72), "navy").save(source)

            manifest = prepare(source, root / "task", scale=2, grid_size=4)

            self.assertEqual((manifest["targetWidth"], manifest["targetHeight"]), (192, 144))
            self.assertEqual((manifest["columns"], manifest["rows"]), (4, 4))
            self.assertEqual(manifest["gridPreset"], "4x4")

    def test_invalid_presets_are_rejected(self) -> None:
        previous_language = get_language()
        set_language(LANG_ZH, persist=False)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "source.png"
                Image.new("RGB", (96, 72), "navy").save(source)
                with self.assertRaisesRegex(ValueError, "放大倍率"):
                    prepare(source, root / "bad-scale", scale=3)
                with self.assertRaisesRegex(ValueError, "分块预设"):
                    prepare(source, root / "bad-grid", grid_size=6)
        finally:
            set_language(previous_language, persist=False)


if __name__ == "__main__":
    unittest.main()
