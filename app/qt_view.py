from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .i18n import LANG_EN, LANG_ZH
from .qt_preview import PreviewCanvas
from .qt_view_text import apply_static_translations
from .qt_widgets import AnimatedProgressBar, DropFrame, SegmentedControl, StatusIndicator


class QtView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        self._build()

    @staticmethod
    def _label(text: str = "", object_name: str = "") -> QLabel:
        label = QLabel(text)
        if object_name:
            label.setObjectName(object_name)
        return label

    @staticmethod
    def _button(object_name: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName(object_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    @staticmethod
    def _divider() -> QFrame:
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(42)
        return divider

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)
        root.addLayout(self._build_header())
        workspace = QHBoxLayout()
        workspace.setSpacing(12)
        workspace.addWidget(self._build_sidebar())
        workspace.addWidget(self._build_preview(), 1)
        root.addLayout(workspace, 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(8)
        self.brand_label = self._label("✦  SEEDVR2", "brand")
        self.heading_label = self._label(object_name="heading")
        header.addWidget(self.brand_label)
        header.addSpacing(10)
        header.addWidget(self.heading_label)
        header.addStretch()
        gpu_badge = QFrame()
        gpu_badge.setStyleSheet("QFrame{background:#DCE7EC;border-radius:8px;}")
        gpu_layout = QHBoxLayout(gpu_badge)
        gpu_layout.setContentsMargins(10, 7, 10, 7)
        gpu_layout.setSpacing(7)
        self.gpu_dot = QLabel("●")
        self.gpu_label = QLabel()
        self.gpu_label.setStyleSheet("font-weight:700;")
        gpu_layout.addWidget(self.gpu_dot)
        gpu_layout.addWidget(self.gpu_label)
        header.addWidget(gpu_badge)
        self.scale_badge = self._label(object_name="badge")
        self.grid_badge = self._label(object_name="badge")
        header.addWidget(self.scale_badge)
        header.addWidget(self.grid_badge)
        header.addWidget(self._label("64 px", "badge"))
        header.addWidget(self._label("LOCAL", "badge"))
        self.language_switch = SegmentedControl([(LANG_ZH, "中文"), (LANG_EN, "EN")])
        self.language_switch.setFixedWidth(96)
        header.addWidget(self.language_switch)
        return header

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("darkPanel")
        sidebar.setFixedWidth(330)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)
        title_row = QHBoxLayout()
        self.task_title = self._label(object_name="sectionTitle")
        self.task_badge = self._label(object_name="darkBadge")
        title_row.addWidget(self.task_title)
        title_row.addStretch()
        title_row.addWidget(self.task_badge)
        layout.addLayout(title_row)
        self.task_subtitle = self._label(object_name="mutedDark")
        self.task_subtitle.setWordWrap(True)
        layout.addWidget(self.task_subtitle)
        layout.addWidget(self._build_input_card())
        layout.addWidget(self._build_output_card())

        warning = QFrame()
        warning.setObjectName("warningCard")
        warning_layout = QHBoxLayout(warning)
        warning_layout.setContentsMargins(10, 9, 10, 9)
        bang = QLabel("!")
        bang.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bang.setFixedSize(26, 26)
        bang.setStyleSheet("background:#DFFF00;color:#151815;font-weight:800;")
        self.warning_label = self._label(object_name="warning")
        self.warning_label.setWordWrap(True)
        warning_layout.addWidget(bang)
        warning_layout.addWidget(self.warning_label, 1)
        layout.addWidget(warning)
        layout.addStretch()

        presets = QHBoxLayout()
        presets.setSpacing(8)
        self.scale_combo, scale_group, self.scale_caption = self._preset_group(["2×", "4×", "6×", "8×"])
        self.grid_combo, grid_group, self.grid_caption = self._preset_group(["", "3×3", "4×4", "5×5"])
        presets.addWidget(scale_group)
        presets.addWidget(grid_group)
        layout.addLayout(presets)
        self.start_button = self._button("primary")
        self.start_button.setMinimumHeight(48)
        layout.addWidget(self.start_button)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.stop_button = self._button("secondary")
        self.open_short_button = self._button("blue")
        actions.addWidget(self.stop_button)
        actions.addWidget(self.open_short_button)
        layout.addLayout(actions)
        return sidebar

    def _preset_group(self, values: list[str]) -> tuple[QComboBox, QFrame, QLabel]:
        group = QFrame()
        group.setObjectName("softPanel")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setSpacing(4)
        caption = self._label(object_name="mutedDark")
        combo = QComboBox()
        combo.addItems(values)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(caption)
        layout.addWidget(combo)
        return combo, group, caption

    def _build_input_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("inputCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)
        self.input_caption = self._label(object_name="lightStrong")
        layout.addWidget(self.input_caption)
        self.input_drop_zone = DropFrame()
        self.input_drop_zone.setObjectName("inputSummary")
        summary = QHBoxLayout(self.input_drop_zone)
        summary.setContentsMargins(8, 8, 8, 8)
        summary.setSpacing(10)
        self.input_thumbnail = QLabel("+")
        self.input_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_thumbnail.setFixedSize(64, 52)
        self.input_thumbnail.setStyleSheet("background:#1E211E;color:#AFC7D4;border-radius:6px;font-size:24px;")
        text = QVBoxLayout()
        self.input_name = self._label(object_name="lightStrong")
        self.input_meta = self._label(object_name="mutedDark")
        self.input_meta.setWordWrap(True)
        self.input_name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(self.input_name)
        text.addWidget(self.input_meta)
        summary.addWidget(self.input_thumbnail)
        summary.addLayout(text, 1)
        layout.addWidget(self.input_drop_zone)
        self.choose_input_button = self._button("secondary")
        layout.addWidget(self.choose_input_button)
        self.size_hint = self._label(object_name="warning")
        self.size_hint.setWordWrap(True)
        layout.addWidget(self.size_hint)
        return card

    def _build_output_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("inputCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)
        self.output_caption = self._label(object_name="lightStrong")
        self.output_path = self._label(object_name="light")
        self.output_path.setWordWrap(True)
        self.output_path.setMaximumHeight(38)
        self.choose_output_button = self._button("secondary")
        layout.addWidget(self.output_caption)
        layout.addWidget(self.output_path)
        layout.addWidget(self.choose_output_button)
        return card

    def _build_preview(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("darkPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(7, 6, 9, 6)
        self.view_switch = SegmentedControl([("input", ""), ("compare", ""), ("output", "")])
        self.preview_hint = self._label(object_name="mutedDark")
        toolbar_layout.addWidget(self.view_switch)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.preview_hint)
        layout.addWidget(toolbar)
        self.preview = PreviewCanvas()
        layout.addWidget(self.preview, 1)
        self.log_panel = QFrame()
        self.log_panel.setObjectName("softPanel")
        log_layout = QVBoxLayout(self.log_panel)
        log_layout.setContentsMargins(10, 8, 10, 10)
        log_header = QHBoxLayout()
        self.log_title = self._label(object_name="lightStrong")
        self.log_live = self._label(object_name="mutedDark")
        log_header.addWidget(self.log_title)
        log_header.addStretch()
        log_header.addWidget(self.log_live)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log_panel.setFixedHeight(132)
        log_layout.addLayout(log_header)
        log_layout.addWidget(self.log)
        self.log_panel.hide()
        layout.addWidget(self.log_panel)
        return panel

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setMinimumHeight(70)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        self.status_indicator = StatusIndicator()
        self.status_label = self._label(object_name="lightStrong")
        self.status_label.setMinimumWidth(130)
        self.progress = AnimatedProgressBar()
        self.progress.setMinimumWidth(150)
        self.progress_percent = self._label("0%", "lightStrong")
        layout.addWidget(self.status_indicator)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress, 1)
        layout.addWidget(self.progress_percent)
        layout.addWidget(self._divider())
        self.output_size_caption = self._label(object_name="mutedDark")
        self.output_size_value = self._label("—", "lightStrong")
        self.output_size_caption.setMinimumWidth(76)
        layout.addLayout(self._metric(self.output_size_caption, self.output_size_value))
        layout.addWidget(self._divider())
        self.elapsed_caption = self._label(object_name="mutedDark")
        self.elapsed_value = self._label("—", "lightStrong")
        layout.addLayout(self._metric(self.elapsed_caption, self.elapsed_value))
        layout.addWidget(self._divider())
        self.log_button = self._button("outline")
        self.open_footer_button = self._button("blue")
        layout.addWidget(self.log_button)
        layout.addWidget(self.open_footer_button)
        return footer

    @staticmethod
    def _metric(caption: QLabel, value: QLabel) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(1)
        layout.addWidget(caption)
        layout.addWidget(value)
        return layout

    def apply_static_translations(self, log_visible: bool) -> None:
        apply_static_translations(self, log_visible)
