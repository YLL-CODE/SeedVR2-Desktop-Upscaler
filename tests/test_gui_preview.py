from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.config import PROJECT_ROOT
from app.gui import (
    CORNER_RADIUS_SCALE,
    PREVIEW_MAX_SIZE,
    _corner,
    calculate_zoom_viewport,
    compact_filename,
    file_details,
    format_duration,
    load_preview_image,
    render_rounded_rectangle,
    validate_input_image_paths,
)
from app.i18n import LANG_ZH, get_language, set_language


class PreviewImageTests(unittest.TestCase):
    def test_zoom_viewport_crops_around_center_without_exceeding_canvas(self) -> None:
        crop, rendered, scale, center = calculate_zoom_viewport((1200, 675), (960, 540), 2.0, (0.5, 0.5))

        self.assertEqual(crop, (300, 168, 900, 506))
        self.assertEqual(rendered, (960, 540))
        self.assertAlmostEqual(scale, 1.6)
        self.assertEqual(center, (0.5, 0.5))

    def test_rectangular_corner_radius_is_reduced_by_35_percent(self) -> None:
        self.assertEqual(CORNER_RADIUS_SCALE, 0.65)
        self.assertEqual(_corner(20), 13)

    def test_preview_is_bounded_and_transparency_is_flattened(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "transparent.png"
            Image.new("RGBA", (1600, 1200), (255, 0, 0, 128)).save(source)

            preview, original_size = load_preview_image(source)

            self.assertEqual(original_size, (1600, 1200))
            self.assertEqual(preview.size, PREVIEW_MAX_SIZE)
            self.assertEqual(preview.mode, "RGB")

    def test_file_details_contains_dimensions_format_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "sample.jpg"
            source.write_bytes(b"x" * 1536)

            self.assertEqual(file_details(source, (1920, 1080)), "1920 × 1080  ·  JPG  ·  2 KB")

    def test_compact_filename_preserves_extension(self) -> None:
        self.assertEqual(compact_filename("short.png"), "short.png")
        self.assertEqual(compact_filename("12345678901234567890123456789.jpeg"), "12345678901234567890….jpeg")

    def test_application_icon_contains_windows_sizes(self) -> None:
        with Image.open(PROJECT_ROOT / "assets" / "seedvr2.ico") as icon:
            self.assertTrue({(16, 16), (32, 32), (48, 48), (256, 256)}.issubset(icon.info["sizes"]))

    def test_rounded_rectangle_contains_antialiased_edge_pixels(self) -> None:
        image = render_rounded_rectangle(120, 44, 16, "#AFC7D4")
        alpha_values = set(image.getchannel("A").getdata())

        self.assertIn(0, alpha_values)
        self.assertIn(255, alpha_values)
        self.assertTrue(any(0 < value < 255 for value in alpha_values))

    def test_duration_is_formatted_like_footer_reference(self) -> None:
        self.assertEqual(format_duration(138), "00:02:18")

    def test_single_supported_input_path_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "sample.WEBP"
            source.touch()

            accepted, error = validate_input_image_paths((str(source),))

            self.assertEqual(accepted, source)
            self.assertEqual(error, "")

    def test_multiple_or_unsupported_input_paths_are_rejected(self) -> None:
        previous_language = get_language()
        set_language(LANG_ZH, persist=False)
        try:
            with tempfile.TemporaryDirectory() as temporary:
                first = Path(temporary) / "one.png"
                second = Path(temporary) / "two.jpg"
                unsupported = Path(temporary) / "notes.txt"
                for source in (first, second, unsupported):
                    source.touch()

                accepted, multiple_error = validate_input_image_paths((str(first), str(second)))
                unsupported_path, unsupported_error = validate_input_image_paths((str(unsupported),))

                self.assertIsNone(accepted)
                self.assertIn("一张图片", multiple_error)
                self.assertIsNone(unsupported_path)
                self.assertIn("仅支持", unsupported_error)
        finally:
            set_language(previous_language, persist=False)


if __name__ == "__main__":
    unittest.main()
