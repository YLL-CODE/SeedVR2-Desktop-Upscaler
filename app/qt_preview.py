from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget


def pil_to_qimage(image: Image.Image) -> QImage:
    rgb = image.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    return QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888).copy()


class PreviewCanvas(QWidget):
    zoomChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewCanvas")
        self.setMinimumSize(420, 360)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.mode = "input"
        self.images: dict[str, QImage | None] = {"input": None, "output": None}
        self.placeholders: dict[str, str] = {"input": "", "output": ""}
        self.titles = {"input": "Original", "output": "Upscaled Result"}
        self.compare_placeholder = ""
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.divider = 0.5
        self.drag_mode = ""
        self.drag_origin = QPoint()
        self.setStyleSheet("QWidget#previewCanvas{background:#181A18;border:0;border-radius:8px;}")

    def set_mode(self, mode: str) -> None:
        if mode not in {"input", "compare", "output"}:
            return
        self.mode = mode
        self.reset_zoom()
        self.update()

    def set_texts(self, input_title: str, output_title: str, compare_placeholder: str) -> None:
        self.titles = {"input": input_title, "output": output_title}
        self.compare_placeholder = compare_placeholder
        self.update()

    def set_image(self, kind: str, image: Image.Image | None, placeholder: str = "") -> None:
        self.images[kind] = pil_to_qimage(image) if image is not None else None
        self.placeholders[kind] = placeholder
        self.reset_zoom()
        self.update()

    def reset_zoom(self) -> None:
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.zoomChanged.emit(100)
        self.update()

    def _available_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(16, 36, -16, -16)

    def _image_rect(self, image: QImage) -> QRectF:
        available = self._available_rect()
        scale = min(available.width() / image.width(), available.height() / image.height()) * self.zoom
        size = QPointF(image.width() * scale, image.height() * scale)
        center = available.center() + self.pan
        return QRectF(center.x() - size.x() / 2, center.y() - size.y() / 2, size.x(), size.y())

    def _draw_image(self, painter: QPainter, image: QImage, target: QRectF) -> None:
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(target, image)

    def _draw_placeholder(self, painter: QPainter, text: str) -> None:
        painter.setPen(QColor("#ADB5AD"))
        painter.drawText(self._available_rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#181A18"))
        painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
        painter.setPen(QColor("#F5F7F3"))

        if self.mode == "compare":
            self._paint_compare(painter)
            return
        kind = "output" if self.mode == "output" else "input"
        painter.drawText(16, 24, self.titles[kind])
        image = self.images[kind]
        if image is None:
            self._draw_placeholder(painter, self.placeholders[kind])
            return
        self._draw_image(painter, image, self._image_rect(image))

    def _paint_compare(self, painter: QPainter) -> None:
        source = self.images["input"]
        output = self.images["output"]
        if source is None or output is None:
            self._draw_placeholder(painter, self.compare_placeholder)
            return
        target = self._image_rect(output)
        split = target.left() + target.width() * self.divider
        painter.save()
        painter.setClipRect(QRectF(target.left(), target.top(), split - target.left(), target.height()))
        self._draw_image(painter, source, target)
        painter.restore()
        painter.save()
        painter.setClipRect(QRectF(split, target.top(), target.right() - split, target.height()))
        self._draw_image(painter, output, target)
        painter.restore()
        painter.setPen(QPen(QColor("#DFFF00"), 2))
        painter.drawLine(QPointF(split, target.top()), QPointF(split, target.bottom()))
        painter.setBrush(QColor("#DFFF00"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(split, target.center().y()), 8, 8)
        painter.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor("#F5F7F3"))
        painter.drawText(QRectF(target.left() + 10, target.top() + 8, 120, 24), self.titles["input"])
        painter.drawText(
            QRectF(target.right() - 130, target.top() + 8, 120, 24),
            Qt.AlignmentFlag.AlignRight,
            self.titles["output"],
        )

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.mode not in {"compare", "output"}:
            event.ignore()
            return
        old_zoom = self.zoom
        self.zoom = max(1.0, min(4.0, self.zoom * (1.2 if event.angleDelta().y() > 0 else 1 / 1.2)))
        if self.zoom == 1.0:
            self.pan = QPointF(0, 0)
        elif old_zoom != self.zoom:
            cursor_delta = QPointF(event.position()) - self._available_rect().center()
            self.pan -= cursor_delta * (self.zoom / old_zoom - 1)
        self.zoomChanged.emit(round(self.zoom * 100))
        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.mode == "compare" and event.button() == Qt.MouseButton.LeftButton:
            self.drag_mode = "divider"
            self._move_divider(event.position().x())
        elif self.mode == "output" and event.button() == Qt.MouseButton.LeftButton:
            self.drag_mode = "pan"
        elif self.mode == "compare" and event.button() == Qt.MouseButton.RightButton:
            self.drag_mode = "pan"
        self.drag_origin = event.position().toPoint()
        self.setFocus()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.drag_mode == "divider":
            self._move_divider(event.position().x())
        elif self.drag_mode == "pan" and self.zoom > 1.0:
            delta = event.position().toPoint() - self.drag_origin
            self.pan += QPointF(delta)
            self.drag_origin = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        self.drag_mode = ""

    def mouseDoubleClickEvent(self, _event: QMouseEvent) -> None:
        if self.mode in {"compare", "output"}:
            self.reset_zoom()

    def _move_divider(self, x: float) -> None:
        available = self._available_rect()
        self.divider = max(0.02, min(0.98, (x - available.left()) / max(1.0, available.width())))
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.mode == "compare" and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.divider = max(0.02, min(0.98, self.divider + (-0.03 if event.key() == Qt.Key.Key_Left else 0.03)))
            self.update()
            return
        super().keyPressEvent(event)
