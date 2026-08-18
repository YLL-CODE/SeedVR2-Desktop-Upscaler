from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from .i18n import tr
from .qt_preview import pil_to_qimage
from .qt_utils import file_details, load_preview_image


def request_preview(controller: Any, kind: str, path: Path | None, placeholder_key: str) -> None:
    controller.preview_generations[kind] += 1
    generation = controller.preview_generations[kind]
    controller.preview_placeholders[kind] = placeholder_key
    controller.view.preview.set_image(kind, None, tr(placeholder_key))
    if path:
        threading.Thread(target=_load_preview, args=(controller, kind, generation, path), daemon=True).start()


def _load_preview(controller: Any, kind: str, generation: int, path: Path) -> None:
    try:
        image, dimensions = load_preview_image(path)
        controller.preview_events.put((kind, generation, image, dimensions, ""))
    except Exception as error:
        controller.preview_events.put((kind, generation, None, None, str(error)))


def poll_previews(controller: Any) -> None:
    while not controller.preview_events.empty():
        _handle_preview(controller, controller.preview_events.get_nowait())


def set_preview_hint(controller: Any) -> None:
    mode, percent = controller.view.preview.mode, round(controller.view.preview.zoom * 100)
    if percent != 100 and mode in {"compare", "output"}:
        text = tr("preview.zoom_reset", percent=percent)
    elif mode == "compare":
        text = tr("preview.compare_help")
    elif mode == "output":
        text = tr("preview.output_help")
    else:
        text = tr("preview.fit")
    controller.view.preview_hint.setText(text)


def _handle_preview(
    controller: Any,
    payload: tuple[str, int, Image.Image | None, tuple[int, int] | None, str],
) -> None:
    kind, generation, image, dimensions, error = payload
    if generation != controller.preview_generations[kind]:
        return
    if image is None or dimensions is None:
        controller.view.preview.set_image(
            kind,
            None,
            tr("preview.error", error=error) if error else tr("preview.unavailable"),
        )
        if kind == "input":
            controller.view.input_meta.setText(tr("input.read_failed"))
            controller.view.input_thumbnail.setText("!")
        return
    controller.view.preview.set_image(kind, image)
    if kind != "input" or not controller.input_path:
        return
    controller.input_dimensions = dimensions
    thumbnail = QPixmap.fromImage(pil_to_qimage(image)).scaled(
        58,
        46,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    controller.view.input_thumbnail.setPixmap(thumbnail)
    controller.view.input_thumbnail.setText("")
    try:
        controller.view.input_meta.setText(file_details(controller.input_path, dimensions))
    except OSError:
        controller.view.input_meta.setText(f"{dimensions[0]} × {dimensions[1]}")
