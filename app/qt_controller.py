from __future__ import annotations

import os
import queue
from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox

from .i18n import LANG_EN, LANG_ZH, load_language, set_language, tr
from .qt_preview_tasks import poll_previews, request_preview, set_preview_hint
from .qt_utils import compact_filename, validate_input_image_paths
from .qt_view import QtView
from .qt_worker_events import handle_worker_event
from .worker_client import WorkerClient


class QtController:
    def __init__(self, window, view: QtView, *, start_worker: bool = True) -> None:  # type: ignore[no-untyped-def]
        self.window = window
        self.view = view
        self.language = load_language()
        set_language(self.language, persist=False)
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.preview_events: queue.Queue[tuple[str, int, Image.Image | None, tuple[int, int] | None, str]] = queue.Queue()
        self.preview_generations = {"input": 0, "output": 0}
        self.preview_placeholders = {"input": "preview.input_empty", "output": "preview.output_empty"}
        self.input_path: Path | None = None
        self.output_dir = Path(os.environ.get("SEEDVR2_OUTPUT_DIR", Path.home() / "Pictures" / "SeedVR2 Upscaler"))
        self.input_dimensions: tuple[int, int] | None = None
        self.last_output: Path | None = None
        self.running = False
        self.preflight_complete = False
        self.memory_profile = "8–16GB"
        self.log_visible = False
        self.log_entries: list[tuple[str | None, dict[str, Any], str]] = []
        self.status_key = "status.worker_starting"
        self.status_values: dict[str, Any] = {}
        self.gpu_key = "status.gpu_detecting"
        self.gpu_values: dict[str, Any] = {}
        self.worker: WorkerClient | None = None
        self._connect()
        self._setup_presets()
        self.refresh_language()
        self._set_controls()
        if start_worker:
            self.worker = WorkerClient(self.events, self.language)
        else:
            self.preflight_complete = True
            self.status_key = "status.worker_ready"
            self.gpu_key = "status.gpu_ready"
            self.gpu_values = {"gpu": "Smoke GPU"}
            self._set_gpu_ready(True)
            self._set_controls()
        self.timer = QTimer(window)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    def _connect(self) -> None:
        v = self.view
        v.choose_input_button.clicked.connect(self.choose_input)
        v.input_drop_zone.clicked.connect(self.choose_input)
        v.input_drop_zone.pathsDropped.connect(self.accept_input_paths)
        v.choose_output_button.clicked.connect(self.choose_output)
        v.start_button.clicked.connect(self.start)
        v.stop_button.clicked.connect(self.stop)
        v.open_short_button.clicked.connect(self.open_output)
        v.open_footer_button.clicked.connect(self.open_output)
        v.log_button.clicked.connect(self.toggle_log)
        v.scale_combo.currentIndexChanged.connect(self.preset_changed)
        v.grid_combo.currentIndexChanged.connect(self.preset_changed)
        v.view_switch.valueChanged.connect(self.set_preview_mode)
        v.language_switch.valueChanged.connect(self.change_language)
        v.preview.zoomChanged.connect(self._zoom_changed)

    def _setup_presets(self) -> None:
        self.view.scale_combo.blockSignals(True)
        self.view.scale_combo.clear()
        for value in (2, 4, 6, 8):
            self.view.scale_combo.addItem(f"{value}×", value)
        self.view.scale_combo.setCurrentIndex(1)
        self.view.scale_combo.blockSignals(False)
        self._rebuild_grid(None)

    def _rebuild_grid(self, selected: int | None) -> None:
        combo = self.view.grid_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr("preset.auto"), "auto")
        for value in (3, 4, 5):
            combo.addItem(f"{value}×{value}", value)
        index = combo.findData("auto" if selected is None else selected)
        combo.setCurrentIndex(max(0, index))
        combo.blockSignals(False)

    def scale(self) -> int:
        return int(self.view.scale_combo.currentData() or 4)

    def grid(self) -> int | None:
        value = self.view.grid_combo.currentData()
        return None if value in {None, "auto"} else int(value)

    def refresh_language(self) -> None:
        v = self.view
        self.window.setWindowTitle(tr("app.title"))
        v.apply_static_translations(self.log_visible)
        v.language_switch.set_value(self.language, False, False)
        self._rebuild_grid(self.grid())
        v.status_label.setText(tr(self.status_key, **self.status_values))
        v.gpu_label.setText(tr(self.gpu_key, **self.gpu_values))
        v.start_button.setText(tr("action.start", scale=self.scale()))
        v.scale_badge.setText(tr("status.scale", scale=self.scale()))
        v.grid_badge.setText(tr("status.grid", grid="AUTO" if self.grid() is None else f"{self.grid()}×{self.grid()}"))
        if self.input_path is None:
            v.input_name.setText(tr("input.none"))
            v.input_meta.setText(tr("input.formats"))
        self._refresh_size_hint()
        v.output_path.setText(str(self.output_dir))
        v.preview.placeholders["input"] = tr(self.preview_placeholders["input"])
        v.preview.placeholders["output"] = tr(self.preview_placeholders["output"])
        self._set_preview_hint()
        self._rebuild_log()

    def change_language(self, language: str) -> None:
        if language == self.language or language not in {LANG_ZH, LANG_EN}:
            return
        self.language = set_language(language, persist=False)
        try:
            set_language(language, persist=True)
        except OSError as error:
            QMessageBox.warning(self.window, tr("dialog.settings_failed"), tr("dialog.settings_failed_message", error=error))
        self.refresh_language()
        if self.worker:
            try:
                self.worker.send({"command": "set_language", "language": language})
            except (OSError, RuntimeError):
                pass

    def preset_changed(self) -> None:
        self.view.start_button.setText(tr("action.start", scale=self.scale()))
        self.view.scale_badge.setText(tr("status.scale", scale=self.scale()))
        grid_text = "AUTO" if self.grid() is None else f"{self.grid()}×{self.grid()}"
        self.view.grid_badge.setText(tr("status.grid", grid=grid_text))
        self._refresh_size_hint()

    def _refresh_size_hint(self) -> None:
        key = "size.high" if self.scale() >= 6 else "size.default"
        text = tr(key, profile=self.memory_profile) if key == "size.default" else tr(key)
        if self.grid() is not None:
            text += tr("size.manual")
        self.view.size_hint.setText(text)

    def choose_input(self) -> None:
        if self.running:
            return
        path, _selected = QFileDialog.getOpenFileName(
            self.window,
            tr("dialog.choose_image"),
            "",
            f"{tr('dialog.image_files')} (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;{tr('dialog.all_files')} (*)",
        )
        if path:
            self.accept_input_paths([path])

    def accept_input_paths(self, paths: list[str]) -> None:
        if self.running:
            QMessageBox.warning(self.window, tr("dialog.change_blocked_title"), tr("dialog.change_blocked"))
            return
        source, error = validate_input_image_paths(paths)
        if source is None:
            QMessageBox.warning(self.window, tr("dialog.add_failed"), error)
            return
        self.input_path = source
        self.input_dimensions = None
        self.last_output = None
        self.view.input_name.setText(compact_filename(source.name))
        self.view.input_meta.setText(tr("input.loading_info"))
        self.view.input_thumbnail.clear()
        self.view.input_thumbnail.setText("…")
        self._set_open_controls(False)
        self.request_preview("input", source, "preview.loading_input")
        self.request_preview("output", None, "preview.output_empty")
        self.set_preview_mode("input")

    def choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self.window, tr("dialog.choose_output"), str(self.output_dir))
        if path:
            self.output_dir = Path(path)
            self.view.output_path.setText(path)

    def start(self) -> None:
        if not self.worker or not self.input_path or not self.input_path.is_file():
            QMessageBox.critical(self.window, tr("dialog.start_failed"), tr("dialog.select_valid"))
            return
        scale, grid = self.scale(), self.grid()
        if scale >= 6:
            estimate = ""
            if self.input_dimensions:
                estimate = tr("dialog.high_scale_output", width=self.input_dimensions[0] * scale, height=self.input_dimensions[1] * scale)
            answer = QMessageBox.warning(
                self.window,
                tr("dialog.high_scale_title"),
                tr("dialog.high_scale", scale=scale, output_size=estimate),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.worker.send({"command": "run", "source": str(self.input_path), "outputDir": str(self.output_dir), "scale": scale, "grid": "auto" if grid is None else grid})
        except Exception as error:
            QMessageBox.critical(self.window, tr("dialog.start_failed"), str(error))
            return
        self.running = True
        self.last_output = None
        self._set_progress(0, True)
        self.view.output_size_value.setText("—")
        self.view.elapsed_value.setText("—")
        self._set_open_controls(False)
        self._set_controls()
        self.request_preview("output", None, "preview.processing")
        self.set_preview_mode("input")

    def stop(self) -> None:
        if self.worker:
            self.worker.send({"command": "cancel"})
        self.status_key, self.status_values = "status.stopping", {}
        self.view.status_label.setText(tr(self.status_key))
        self.view.stop_button.setEnabled(False)

    def open_output(self) -> None:
        target = self.last_output.parent if self.last_output else self.output_dir
        if target.is_dir():
            os.startfile(target)

    def toggle_log(self) -> None:
        self.log_visible = not self.log_visible
        self.view.log_panel.setVisible(self.log_visible)
        self.view.log_button.setText(tr("action.hide_log" if self.log_visible else "action.view_log"))

    def set_preview_mode(self, mode: str) -> None:
        self.view.view_switch.set_value(mode, True, False)
        self.view.preview.set_mode(mode)
        self._set_preview_hint()

    def _zoom_changed(self, _percent: int) -> None:
        self._set_preview_hint()

    def _set_preview_hint(self) -> None:
        set_preview_hint(self)

    def _set_controls(self) -> None:
        editable = not self.running
        self.view.choose_input_button.setEnabled(editable)
        self.view.input_drop_zone.setEnabled(editable)
        self.view.choose_output_button.setEnabled(editable)
        self.view.scale_combo.setEnabled(editable)
        self.view.grid_combo.setEnabled(editable)
        self.view.start_button.setEnabled(editable and self.preflight_complete)
        self.view.stop_button.setEnabled(self.running)

    def _set_open_controls(self, enabled: bool) -> None:
        self.view.open_short_button.setEnabled(enabled)
        self.view.open_footer_button.setEnabled(enabled)

    def _set_gpu_ready(self, ready: bool) -> None:
        self.view.gpu_dot.setStyleSheet(f"color:{'#45C96B' if ready else '#FF5F57'};font-size:11px;")

    def _set_progress(self, value: float, active: bool | None = None) -> None:
        self.view.progress.setValue(value)
        self.view.progress_percent.setText(f"{round(max(0, min(100, value)))}%")
        if active is not None:
            self.view.progress.setActive(active)

    def append_log(self, text: str = "", key: str | None = None, values: dict[str, Any] | None = None) -> None:
        values = values or {}
        self.log_entries.append((key, values, text))
        self.view.log.appendPlainText(tr(key, **values) if key else text)

    def _rebuild_log(self) -> None:
        self.view.log.setPlainText("\n".join(tr(key, **values) if key else text for key, values, text in self.log_entries))

    def request_preview(self, kind: str, path: Path | None, placeholder_key: str) -> None:
        request_preview(self, kind, path, placeholder_key)

    def poll(self) -> None:
        while not self.events.empty():
            handle_worker_event(self, self.events.get_nowait())
        poll_previews(self)

    def close(self) -> None:
        self.timer.stop()
        self.view.progress.setActive(False)
        if self.worker:
            self.worker.close()
