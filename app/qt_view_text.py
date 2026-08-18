from __future__ import annotations

from typing import Any

from .i18n import tr


def apply_static_translations(view: Any, log_visible: bool) -> None:
    view.heading_label.setText(tr("app.heading"))
    view.task_title.setText(tr("task.new"))
    view.task_badge.setText(tr("task.single"))
    view.task_subtitle.setText(tr("task.subtitle"))
    view.warning_label.setText(tr("task.warning"))
    view.scale_caption.setText(tr("preset.scale"))
    view.grid_caption.setText(tr("preset.grid"))
    view.input_caption.setText(tr("input.label"))
    view.output_caption.setText(tr("output.label"))
    view.choose_input_button.setText(tr("action.choose_image"))
    view.choose_output_button.setText(tr("action.change"))
    view.stop_button.setText(tr("action.stop"))
    view.open_short_button.setText(tr("action.open_output_short"))
    view.log_button.setText(tr("action.hide_log" if log_visible else "action.view_log"))
    view.open_footer_button.setText(tr("action.open_output"))
    view.log_title.setText(tr("log.title"))
    view.log_live.setText(tr("log.live"))
    view.output_size_caption.setText(tr("footer.output_size"))
    view.elapsed_caption.setText(tr("footer.elapsed"))
    view.view_switch.set_options(
        [("input", tr("view.input")), ("compare", tr("view.compare")), ("output", tr("view.output"))]
    )
    view.preview.set_texts(tr("preview.input_title"), tr("preview.output_title"), tr("preview.compare_empty"))
