from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QMessageBox

from .i18n import tr
from .qt_preview_tasks import request_preview
from .qt_utils import format_duration


def _message(event: dict[str, Any]) -> tuple[str, str | None, dict[str, Any]]:
    key, values = event.get("messageKey"), event.get("messageArgs")
    if isinstance(key, str) and isinstance(values, dict):
        return tr(key, **values), key, values
    return str(event.get("message", "")), None, {}


def handle_worker_event(controller: Any, event: dict[str, Any]) -> None:
    name = event.get("event")
    message, key, values = _message(event)
    if name == "ready" and controller.worker:
        controller.status_key, controller.status_values = "status.checking_cuda", {}
        controller.view.status_label.setText(tr(controller.status_key))
        controller.worker.send({"command": "self_check", "withCuda": True})
    elif name == "self_check":
        system = event.get("result", {}).get("system", {})
        gpu = str(system.get("gpu", "CUDA")).replace("NVIDIA GeForce ", "")
        controller.status_key, controller.status_values = "status.worker_ready", {}
        controller.gpu_key, controller.gpu_values = "status.gpu_ready", {"gpu": gpu}
        controller.memory_profile = str(system.get("memoryProfile", "8–16GB"))
        controller.preflight_complete = True
        controller._set_gpu_ready(True)
        controller.refresh_language()
        controller._set_controls()
    elif name in {"status", "progress", "model_ready", "system_ready", "cancel_requested"}:
        controller.status_key, controller.status_values = (key, values) if key else ("", {})
        controller.view.status_label.setText(message)
        controller._set_progress(float(event.get("progress", controller.view.progress.value() / 100)) * 100)
        if name == "status" and event.get("stage") == "assemble":
            controller.view.stop_button.setEnabled(False)
        controller.append_log(message, key, values)
    elif name == "completed":
        _complete(controller, event)
    elif name == "cancelled":
        controller.running = False
        controller.status_key, controller.status_values = "status.cancelled", {}
        controller.view.status_label.setText(tr(controller.status_key))
        controller.view.status_indicator.setState("error")
        controller._set_progress(controller.view.progress.value(), False)
        controller._set_controls()
        request_preview(controller, "output", None, "preview.no_result")
        controller.set_preview_mode("input")
    elif name == "error":
        _fail(controller, message, event)
    elif name == "worker_log" and message:
        controller.append_log(message)


def _complete(controller: Any, event: dict[str, Any]) -> None:
    controller.running = False
    controller.last_output = Path(event["output"])
    metrics = event["metrics"]
    controller.status_key, controller.status_values = "status.completed", {}
    controller.view.status_label.setText(tr(controller.status_key))
    controller.view.status_indicator.setState("success")
    controller.view.output_size_value.setText(f"{metrics['outputSize'][0]} × {metrics['outputSize'][1]}")
    controller.view.elapsed_value.setText(format_duration(metrics["timings"]["wallSeconds"]))
    controller._set_progress(100, False)
    controller._set_controls()
    controller._set_open_controls(True)
    controller.append_log(str(controller.last_output))
    request_preview(controller, "output", controller.last_output, "preview.loading_output")
    controller.set_preview_mode("compare")


def _fail(controller: Any, message: str, event: dict[str, Any]) -> None:
    was_running = controller.running
    controller.running = False
    controller.status_key, controller.status_values = "status.failed", {}
    controller.view.status_label.setText(tr(controller.status_key))
    controller.view.status_indicator.setState("error")
    controller._set_progress(controller.view.progress.value(), False)
    if not controller.preflight_complete:
        controller.gpu_key, controller.gpu_values = "status.gpu_unavailable", {}
        controller.view.gpu_label.setText(tr(controller.gpu_key))
        controller._set_gpu_ready(False)
    controller._set_controls()
    controller.append_log(message)
    if event.get("log"):
        controller.append_log(key="log.path", values={"path": event["log"]})
    if was_running:
        request_preview(controller, "output", None, "preview.no_result")
        controller.set_preview_mode("input")
    if not controller.log_visible:
        controller.toggle_log()
    QMessageBox.critical(controller.window, tr("dialog.processing_failed"), message)
