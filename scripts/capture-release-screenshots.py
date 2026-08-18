from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = PROJECT_ROOT / "docs" / "images"


def wait_until(app: object, predicate: object, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()  # type: ignore[attr-defined]
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(0.05)
    return False


def main() -> int:
    os.chdir(PROJECT_ROOT)
    sys.path.insert(0, str(PROJECT_ROOT))
    os.environ["SEEDVR2_LANGUAGE"] = "zh_CN"
    os.environ["SEEDVR2_OUTPUT_DIR"] = r"D:\Pictures\SeedVR2 Upscaler"
    with tempfile.TemporaryDirectory(prefix="seedvr2_release_screens_") as temporary:
        os.environ["SEEDVR2_SETTINGS_PATH"] = str(Path(temporary) / "settings.json")

        from PySide6.QtWidgets import QApplication

        from app.i18n import LANG_EN
        from app.qt_main_window import MainWindow
        from app.qt_style import APP_STYLE

        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("SeedVR2 Upscaler")
        app.setStyle("Fusion")
        app.setStyleSheet(APP_STYLE)
        window = MainWindow(start_worker=True)
        window.resize(1120, 780)
        window.show()

        if not wait_until(app, lambda: window.controller.preflight_complete):
            window.close()
            raise RuntimeError("CUDA preflight did not finish before the screenshot timeout")

        wait_until(app, lambda: False, timeout=0.4)
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(IMAGES_DIR / "app-main.png"), "PNG"):
            raise RuntimeError("Could not save the Chinese application screenshot")

        window.controller.change_language(LANG_EN)
        wait_until(app, lambda: False, timeout=0.8)
        if not window.grab().save(str(IMAGES_DIR / "app-main-en.png"), "PNG"):
            raise RuntimeError("Could not save the English application screenshot")

        window.close()
        app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
