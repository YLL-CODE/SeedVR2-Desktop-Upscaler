from __future__ import annotations

import statistics
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

from .config import PROJECT_ROOT
from .qt_controller import QtController
from .qt_style import APP_STYLE
from .qt_view import QtView


class MainWindow(QMainWindow):
    def __init__(self, *, start_worker: bool = True) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(str(PROJECT_ROOT / "assets" / "seedvr2.ico")))
        self.resize(1120, 780)
        self.setMinimumSize(1040, 720)
        self.view = QtView()
        self.setCentralWidget(self.view)
        self.controller = QtController(self, self.view, start_worker=start_worker)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.controller.close()
        super().closeEvent(event)


def resize_benchmark(app: QApplication, window: MainWindow) -> tuple[float, float]:
    samples: list[float] = []
    for index in range(100):
        started = time.perf_counter()
        window.resize(1040 + (index % 20) * 18, 720 + (index % 15) * 10)
        app.processEvents()
        samples.append((time.perf_counter() - started) * 1000)
    return statistics.median(samples), statistics.quantiles(samples, n=20)[18]


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SeedVR2 Upscaler")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    smoke = "--smoke-test" in sys.argv
    window = MainWindow(start_worker=not smoke)
    window.show()
    if smoke:
        app.processEvents()
        view = window.view
        if not all((view.start_button, view.preview, view.progress, view.language_switch, view.input_drop_zone)):
            raise RuntimeError("Qt GUI smoke check failed")
        view.view_switch.set_value("compare", False)
        if view.preview.mode != "compare":
            raise RuntimeError("Qt preview switch smoke check failed")
        median, p95 = resize_benchmark(app, window)
        print(f"qt_gui_smoke=ok resize_median_ms={median:.3f} resize_p95_ms={p95:.3f}")
        if p95 > 33:
            raise RuntimeError(f"Qt resize p95 exceeded 33 ms: {p95:.3f}")
        QTimer.singleShot(0, window.close)
    raise SystemExit(app.exec())
