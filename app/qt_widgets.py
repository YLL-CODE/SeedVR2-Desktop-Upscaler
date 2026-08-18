from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QFrame, QPushButton, QWidget

from .qt_style import COLORS


class DropFrame(QFrame):
    clicked = Signal()
    pathsDropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def dragEnterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.pathsDropped.emit([url.toLocalFile() for url in event.mimeData().urls()])
        event.acceptProposedAction()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class SegmentedControl(QWidget):
    valueChanged = Signal(str)

    def __init__(self, options: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.options = options
        self.value = options[0][0]
        self.setFixedHeight(38)
        self.setMinimumWidth(270)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.indicator = QFrame(self)
        self.indicator.setStyleSheet("background:#AFC7D4; border-radius:7px;")
        self.buttons: list[QPushButton] = []
        self.animation = QPropertyAnimation(self.indicator, b"geometry", self)
        self.animation.setDuration(145)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setStyleSheet("background:#2E312E; border-radius:9px;")
        self._build_buttons()

    def _build_buttons(self) -> None:
        for button in self.buttons:
            button.hide()
            button.deleteLater()
        self.buttons = []
        for key, label in self.options:
            button = QPushButton(label, self)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton{background:transparent;color:#F5F7F3;border:0;padding:0;font-weight:700;}"
                "QPushButton:checked{color:#151815;} QPushButton:focus{border:1px solid #86A6B6;}"
            )
            button.clicked.connect(lambda _checked=False, value=key: self.set_value(value))
            button.show()
            self.buttons.append(button)
        self._layout_children()

    def set_options(self, options: list[tuple[str, str]]) -> None:
        current = self.value
        self.options = options
        self._build_buttons()
        self.set_value(current if any(key == current for key, _ in options) else options[0][0], False)

    def set_value(self, value: str, animate: bool = True, emit: bool = True) -> None:
        keys = [key for key, _ in self.options]
        if value not in keys:
            return
        changed = value != self.value
        self.value = value
        index = keys.index(value)
        for button_index, button in enumerate(self.buttons):
            button.setChecked(button_index == index)
        target = self._indicator_rect(index)
        if animate and self.isVisible():
            self.animation.stop()
            self.animation.setStartValue(self.indicator.geometry())
            self.animation.setEndValue(target)
            self.animation.start()
        else:
            self.indicator.setGeometry(target)
        if changed and emit:
            self.valueChanged.emit(value)

    def _indicator_rect(self, index: int) -> QRect:
        count = max(1, len(self.options))
        inner = self.rect().adjusted(4, 4, -4, -4)
        segment_width = inner.width() // count
        left = inner.left() + index * segment_width
        width = segment_width if index < count - 1 else inner.right() - left + 1
        return QRect(left, inner.top(), width, inner.height())

    def _layout_children(self) -> None:
        count = max(1, len(self.buttons))
        inner = self.rect().adjusted(4, 4, -4, -4)
        segment_width = inner.width() // count
        for index, button in enumerate(self.buttons):
            left = inner.left() + index * segment_width
            width = segment_width if index < count - 1 else inner.right() - left + 1
            button.setGeometry(left, inner.top(), width, inner.height())
            button.raise_()
        if self.options:
            self.indicator.setGeometry(self._indicator_rect([key for key, _ in self.options].index(self.value)))
            self.indicator.lower()

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._layout_children()
        super().resizeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        keys = [key for key, _ in self.options]
        index = keys.index(self.value)
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.set_value(keys[(index - 1) % len(keys)])
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.set_value(keys[(index + 1) % len(keys)])
        else:
            super().keyPressEvent(event)


class AnimatedProgressBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._phase = 0.0
        self._active = False
        self.setFixedHeight(12)
        self.timer = QTimer(self)
        self.timer.setInterval(32)
        self.timer.timeout.connect(self._tick)

    def setValue(self, value: float) -> None:
        self._value = max(0.0, min(100.0, float(value)))
        self.update()

    def value(self) -> float:
        return self._value

    def setActive(self, active: bool) -> None:
        self._active = active
        self.timer.start() if active else self.timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.035) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = self.rect().adjusted(0, 2, 0, -2)
        radius = track.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3A3D3A"))
        painter.drawRoundedRect(track, radius, radius)
        width = round(track.width() * self._value / 100)
        if width <= 0:
            return
        fill = QRect(track.left(), track.top(), width, track.height())
        painter.setBrush(QColor(COLORS["accent"]))
        painter.drawRoundedRect(fill, radius, radius)
        if self._active and width > 24:
            shine_x = fill.left() + round((width + 28) * self._phase) - 28
            painter.setBrush(QColor(255, 255, 255, 70))
            painter.drawRoundedRect(QRect(shine_x, fill.top(), 28, fill.height()), radius, radius)


class StatusIndicator(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = "idle"
        self.setFixedSize(26, 26)

    def setState(self, state: str) -> None:
        self.state = state
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(COLORS["accent"] if self.state == "success" else "#FF8A80" if self.state == "error" else "#7E8982")
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self.rect().adjusted(3, 3, -3, -3))
        if self.state == "success":
            painter.drawLine(7, 13, 11, 17)
            painter.drawLine(11, 17, 19, 9)
        elif self.state == "error":
            painter.drawLine(13, 7, 13, 15)
            painter.drawPoint(13, 19)
        else:
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(10, 10, 6, 6)
