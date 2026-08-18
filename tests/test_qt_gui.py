from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication

from app.i18n import LANG_EN
from app.qt_main_window import MainWindow, resize_benchmark


class QtGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.previous_settings = os.environ.get("SEEDVR2_SETTINGS_PATH")
        os.environ["SEEDVR2_SETTINGS_PATH"] = str(Path(self.temporary.name) / "settings.json")
        self.window = MainWindow(start_worker=False)
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()
        if self.previous_settings is None:
            os.environ.pop("SEEDVR2_SETTINGS_PATH", None)
        else:
            os.environ["SEEDVR2_SETTINGS_PATH"] = self.previous_settings
        self.temporary.cleanup()

    def test_preview_load_and_live_resize_remain_responsive(self) -> None:
        source = Path(self.temporary.name) / "sample.png"
        Image.new("RGB", (640, 360), "#AFC7D4").save(source)

        self.window.controller.accept_input_paths([str(source)])
        deadline = time.monotonic() + 2
        while self.window.controller.input_dimensions is None and time.monotonic() < deadline:
            self.window.controller.poll()
            self.app.processEvents()
            time.sleep(0.01)

        self.assertEqual(self.window.controller.input_dimensions, (640, 360))
        self.assertFalse(self.window.view.preview.images["input"].isNull())
        self.window.view.view_switch.set_value("compare", False)
        self.assertEqual(self.window.view.preview.mode, "compare")
        _median, p95 = resize_benchmark(self.app, self.window)
        self.assertLessEqual(p95, 33)

    def test_language_switch_hides_replaced_segment_buttons_immediately(self) -> None:
        old_buttons = list(self.window.view.view_switch.buttons)

        self.window.controller.change_language(LANG_EN)

        self.assertTrue(all(not button.isVisible() for button in old_buttons))
        self.assertEqual(
            [button.text() for button in self.window.view.view_switch.buttons],
            ["Original", "Compare", "Result"],
        )


if __name__ == "__main__":
    unittest.main()
