from __future__ import annotations

import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox
from typing import Any

from PIL import Image, ImageDraw, ImageOps, ImageTk
from ._vendor.tkinterdnd2 import DND_FILES, TkinterDnD

from .config import PROJECT_ROOT, runtime_python
from .i18n import LANG_EN, LANG_ZH, load_language, set_language, tr, translated_values


COLORS = {
    "background": "#EEF3F1",
    "surface": "#F8FAF9",
    "surface_soft": "#DCE7EC",
    "surface_dark": "#242624",
    "surface_dark_soft": "#343733",
    "surface_blue": "#AFC7D4",
    "accent": "#DFFF00",
    "text": "#151815",
    "text_on_dark": "#F5F7F3",
    "text_muted": "#667069",
    "text_muted_dark": "#ADB5AD",
    "border": "#D5DEDA",
    "warning": "#A96600",
}
FONT = "Microsoft YaHei UI"
PREVIEW_MAX_SIZE = (1200, 900)
UI_SCALE = 1.0
CORNER_RADIUS_SCALE = 0.65
SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})


def enable_windows_dpi_awareness() -> float:
    global UI_SCALE
    if sys.platform != "win32":
        return UI_SCALE
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass
    try:
        UI_SCALE = min(3.0, max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0))
    except (AttributeError, OSError, ZeroDivisionError):
        UI_SCALE = 1.0
    return UI_SCALE


def _ui(value: int | float) -> int:
    return max(1, round(float(value) * UI_SCALE))


def _corner(value: int | float) -> int:
    return max(1, round(_ui(value) * CORNER_RADIUS_SCALE))


def render_rounded_rectangle(
    width: int,
    height: int,
    radius: int,
    fill: str,
    outline: str = "",
    outline_width: int = 0,
) -> Image.Image:
    width = max(1, int(width))
    height = max(1, int(height))
    radius = max(1, min(int(radius), width // 2, height // 2))
    factor = 3 if width * height <= 300_000 else 2
    image = Image.new("RGBA", (width * factor, height * factor), (0, 0, 0, 0))
    drawing = ImageDraw.Draw(image)
    drawing.rounded_rectangle(
        (0, 0, width * factor - 1, height * factor - 1),
        radius=radius * factor,
        fill=fill,
        outline=outline or None,
        width=max(1, outline_width * factor) if outline else 1,
    )
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _begin_aa_draw(canvas: tk.Canvas) -> None:
    canvas._aa_shape_images = []  # type: ignore[attr-defined]


def _draw_aa_round_rect(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int,
    *,
    fill: str,
    outline: str = "",
    width: int = 0,
    tags: str,
) -> int:
    left, top = min(x1, x2), min(y1, y2)
    image = render_rounded_rectangle(
        abs(x2 - x1) + 1,
        abs(y2 - y1) + 1,
        radius,
        fill,
        outline,
        width,
    )
    photo = ImageTk.PhotoImage(image, master=canvas)
    images = getattr(canvas, "_aa_shape_images", None)
    if images is None:
        images = []
        canvas._aa_shape_images = images  # type: ignore[attr-defined]
    images.append(photo)
    return canvas.create_image(left, top, image=photo, anchor="nw", tags=tags)


class RoundedPanel(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        color: str,
        radius: int = 24,
        padding: int = 18,
        **kwargs: Any,
    ) -> None:
        for dimension in ("width", "height"):
            if dimension in kwargs:
                kwargs[dimension] = _ui(kwargs[dimension])
        super().__init__(
            parent,
            background=parent.cget("background"),
            borderwidth=0,
            highlightthickness=0,
            **kwargs,
        )
        self.color = color
        self.radius = _corner(radius)
        self.padding = max(_ui(padding), max(1, _ui(radius) // 4))
        self.content = tk.Frame(self, background=color, borderwidth=0)
        self._content_window = self.create_window(self.padding, self.padding, anchor="nw", window=self.content)
        self.bind("<Configure>", self._resize)

    def _resize(self, event: tk.Event[tk.Misc]) -> None:
        width = max(2, event.width)
        height = max(2, event.height)
        self.itemconfigure(
            self._content_window,
            width=max(1, width - self.padding * 2),
            height=max(1, height - self.padding * 2),
        )
        self.delete("panel")
        self._rounded_rectangle(1, 1, width - 1, height - 1)
        self.tag_lower("panel")

    def _rounded_rectangle(self, x1: int, y1: int, x2: int, y2: int) -> None:
        _begin_aa_draw(self)
        _draw_aa_round_rect(
            self,
            x1,
            y1,
            x2,
            y2,
            self.radius,
            fill=self.color,
            tags="panel",
        )


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Any,
        *,
        background: str,
        foreground: str,
        active_background: str,
        state: str = "normal",
        border_color: str = "",
        border_width: int = 0,
        icon: str = "",
    ) -> None:
        super().__init__(
            parent,
            background=parent.cget("background"),
            borderwidth=0,
            highlightthickness=0,
            width=_ui(max(86, len(text) * 14 + 24 + (24 if icon else 0))),
            height=_ui(28),
            takefocus=True,
        )
        self.text = text
        self.command = command
        self.button_background = background
        self.foreground = foreground
        self.active_background = active_background
        self.border_color = border_color
        self.border_width = border_width
        self.icon = icon
        self.state = state
        self.hovered = False
        self.pressed = False
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<KeyPress-space>", self._key_press)
        self.bind("<KeyRelease-space>", self._key_release)
        self.bind("<KeyRelease-Return>", self._key_release)
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)
        self._sync_cursor()

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        enabled = self.state == "normal"
        fill = self.active_background if enabled and (self.hovered or self.pressed) else self.button_background
        focused = self.focus_get() is self
        outline = (
            COLORS["text"] if focused and self.button_background == COLORS["accent"] else COLORS["accent"]
        ) if focused else self.border_color
        outline_width = _ui(2) if focused else _ui(self.border_width) if outline else 0
        self.delete("button")
        _begin_aa_draw(self)
        _draw_aa_round_rect(
            self,
            1,
            1,
            width - 1,
            height - 1,
            _corner(14),
            fill=fill,
            outline=outline,
            width=outline_width,
            tags="button",
        )
        text_color = self.foreground if enabled else "#7A807A"
        font_spec = (FONT, 9, "bold")
        if self.icon:
            measured = tkfont.Font(root=self, font=font_spec).measure(self.text)
            icon_size = _ui(16)
            gap = _ui(8)
            group_left = (width - measured - icon_size - gap) // 2
            self._draw_icon(group_left, height // 2, icon_size, text_color)
            text_x = group_left + icon_size + gap
            anchor = "w"
        else:
            text_x = width // 2
            anchor = "center"
        self.create_text(
            text_x,
            height // 2,
            text=self.text,
            fill=text_color,
            font=font_spec,
            anchor=anchor,
            tags="button",
        )

    def _draw_icon(self, left: int, center_y: int, size: int, color: str) -> None:
        stroke = _ui(1.4)
        top = center_y - size // 2
        right = left + size
        bottom = top + size
        if self.icon == "folder":
            self.create_line(
                left,
                top + _ui(4),
                left + _ui(6),
                top + _ui(4),
                left + _ui(8),
                top + _ui(7),
                right,
                top + _ui(7),
                right,
                bottom - _ui(2),
                left,
                bottom - _ui(2),
                left,
                top + _ui(4),
                fill=color,
                width=stroke,
                joinstyle="round",
                capstyle="round",
                tags="button",
            )
        elif self.icon == "log":
            self.create_line(
                left + _ui(2),
                top + _ui(1),
                right - _ui(4),
                top + _ui(1),
                right - _ui(1),
                top + _ui(4),
                right - _ui(1),
                bottom - _ui(2),
                left + _ui(2),
                bottom - _ui(2),
                left + _ui(2),
                top + _ui(1),
                fill=color,
                width=stroke,
                joinstyle="round",
                capstyle="round",
                tags="button",
            )
            for offset in (6, 10):
                self.create_line(
                    left + _ui(5),
                    top + _ui(offset),
                    right - _ui(4),
                    top + _ui(offset),
                    fill=color,
                    width=stroke,
                    capstyle="round",
                    tags="button",
                )

    def _sync_cursor(self) -> None:
        enabled = self.state == "normal"
        super().configure(cursor="hand2" if enabled else "arrow", takefocus=1 if enabled else 0)

    def _enter(self, _event: tk.Event[tk.Misc]) -> None:
        if self.state == "normal":
            self.hovered = True
            self._draw()

    def _leave(self, _event: tk.Event[tk.Misc]) -> None:
        self.hovered = False
        self.pressed = False
        self._draw()

    def _press(self, _event: tk.Event[tk.Misc]) -> None:
        if self.state == "normal":
            self.focus_set()
            self.pressed = True
            self._draw()

    def _release(self, _event: tk.Event[tk.Misc]) -> None:
        if self.state == "normal" and self.pressed:
            self.pressed = False
            self._draw()
            self.command()

    def _key_press(self, _event: tk.Event[tk.Misc]) -> str:
        if self.state == "normal":
            self.pressed = True
            self._draw()
        return "break"

    def _key_release(self, _event: tk.Event[tk.Misc]) -> str:
        if self.state == "normal":
            self.pressed = False
            self._draw()
            self.command()
        return "break"

    def configure(self, cnf: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        options = dict(cnf or {})
        options.update(kwargs)
        redraw = False
        for option, attribute in {
            "text": "text",
            "button_background": "button_background",
            "foreground": "foreground",
            "active_background": "active_background",
            "border_color": "border_color",
            "border_width": "border_width",
            "icon": "icon",
        }.items():
            if option in options:
                setattr(self, attribute, options.pop(option))
                redraw = True
        if "state" in options:
            state = options.pop("state")
            if state not in {"normal", "disabled"}:
                raise tk.TclError(f'bad state "{state}": must be normal or disabled')
            self.state = state
            self.hovered = False
            self.pressed = False
            self._sync_cursor()
            redraw = True
        result = super().configure(**options)
        if redraw:
            self._draw()
        return result

    config = configure

    def cget(self, key: str) -> Any:
        return self.state if key == "state" else super().cget(key)


class AnimatedDropdown(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        variable: tk.StringVar,
        values: tuple[str, ...],
        command: Any,
    ) -> None:
        super().__init__(
            parent,
            background=parent.cget("background"),
            borderwidth=0,
            highlightthickness=0,
            height=_ui(28),
            takefocus=True,
        )
        self.variable = variable
        self.values = values
        self.command = command
        self.state = "readonly"
        self.hovered = False
        self.popup: tk.Toplevel | None = None
        self.listbox: tk.Listbox | None = None
        self.variable.trace_add("write", lambda *_: self._draw())
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._toggle)
        self.bind("<KeyRelease-space>", self._toggle)
        self.bind("<KeyRelease-Return>", self._toggle)
        self.bind("<Alt-KeyPress-Down>", self._toggle)
        self.bind("<KeyPress-Up>", lambda _event: self._cycle(-1))
        self.bind("<KeyPress-Down>", lambda _event: self._cycle(1))
        self.bind("<KeyPress-Escape>", lambda _event: self._close_popup())
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)
        self._sync_cursor()

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        enabled = self.state == "readonly"
        active = enabled and (self.hovered or self.popup is not None or self.focus_get() is self)
        self.delete("dropdown")
        _begin_aa_draw(self)
        _draw_aa_round_rect(
            self,
            1,
            1,
            width - 1,
            height - 1,
            _corner(10),
            fill="#393D39" if enabled else COLORS["surface_dark_soft"],
            outline=COLORS["accent"] if active else "#59615B",
            width=_ui(2 if active else 1),
            tags="dropdown",
        )
        self.create_text(
            _ui(11),
            height // 2,
            text=self.variable.get(),
            anchor="w",
            fill=COLORS["text_on_dark"] if enabled else "#7A807A",
            font=(FONT, 8, "bold"),
            tags="dropdown",
        )
        center_x = width - _ui(13)
        if self.popup is None:
            points = (
                center_x - _ui(4),
                height // 2 - _ui(2),
                center_x + _ui(4),
                height // 2 - _ui(2),
                center_x,
                height // 2 + _ui(3),
            )
        else:
            points = (
                center_x - _ui(4),
                height // 2 + _ui(2),
                center_x + _ui(4),
                height // 2 + _ui(2),
                center_x,
                height // 2 - _ui(3),
            )
        self.create_polygon(
            points,
            fill=COLORS["accent"] if active else COLORS["text_muted_dark"],
            outline="",
            tags="dropdown",
        )

    def _sync_cursor(self) -> None:
        enabled = self.state == "readonly"
        super().configure(cursor="hand2" if enabled else "arrow", takefocus=1 if enabled else 0)

    def _enter(self, _event: tk.Event[tk.Misc]) -> None:
        self.hovered = True
        self._draw()

    def _leave(self, _event: tk.Event[tk.Misc]) -> None:
        self.hovered = False
        self._draw()

    def _toggle(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        if self.state != "readonly":
            return "break"
        self.focus_set()
        if self.popup is None:
            self._open_popup()
        else:
            self._close_popup()
        return "break"

    def _cycle(self, direction: int) -> str:
        if self.state != "readonly":
            return "break"
        try:
            index = self.values.index(self.variable.get())
        except ValueError:
            index = 0
        self.variable.set(self.values[(index + direction) % len(self.values)])
        self.command()
        return "break"

    def set_values(self, values: tuple[str, ...], *, selected: str | None = None) -> None:
        self._close_popup(animate=False)
        self.values = values
        self.variable.set(selected if selected in values else values[0])
        self._draw()

    def _open_popup(self) -> None:
        if self.popup is not None or self.state != "readonly":
            return
        popup = tk.Toplevel(self)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.transient(self.winfo_toplevel())
        popup.configure(background="#59615B")
        try:
            popup.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        frame = tk.Frame(
            popup,
            background="#2E312E",
            highlightthickness=1,
            highlightbackground="#59615B",
        )
        frame.pack(fill="both", expand=True)
        listbox = tk.Listbox(
            frame,
            background="#2E312E",
            foreground=COLORS["text_on_dark"],
            selectbackground=COLORS["accent"],
            selectforeground=COLORS["text"],
            activestyle="none",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            exportselection=False,
            font=(FONT, 9, "bold"),
            cursor="hand2",
            height=len(self.values),
        )
        listbox.pack(fill="both", expand=True, padx=_ui(2), pady=_ui(2))
        for value in self.values:
            listbox.insert("end", value)
        try:
            selected = self.values.index(self.variable.get())
        except ValueError:
            selected = 0
        listbox.selection_set(selected)
        listbox.activate(selected)
        listbox.see(selected)
        listbox.bind("<Motion>", self._hover_option)
        listbox.bind("<ButtonRelease-1>", self._choose_option)
        listbox.bind("<KeyRelease-Return>", self._choose_option)
        listbox.bind("<KeyPress-Escape>", lambda _event: self._close_popup())
        popup.bind("<FocusOut>", self._popup_focus_out)
        self.popup = popup
        self.listbox = listbox
        popup.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + _ui(4)
        width = max(self.winfo_width(), _ui(92))
        full_height = max(_ui(36), len(self.values) * _ui(27) + _ui(6))
        popup.geometry(f"{width}x1+{x}+{y}")
        popup.deiconify()
        popup.lift()
        self._draw()

        def animate(frame_index: int = 0) -> None:
            if self.popup is not popup or not popup.winfo_exists():
                return
            progress = min(1.0, (frame_index + 1) / 8)
            eased = 1 - (1 - progress) ** 3
            popup.geometry(f"{width}x{max(1, round(full_height * eased))}+{x}+{y}")
            try:
                popup.attributes("-alpha", 0.35 + 0.65 * eased)
            except tk.TclError:
                pass
            if progress < 1:
                self.after(16, animate, frame_index + 1)
            else:
                listbox.focus_set()

        animate()

    def _hover_option(self, event: tk.Event[tk.Listbox]) -> None:
        if self.listbox is None:
            return
        index = self.listbox.nearest(event.y)
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(index)
        self.listbox.activate(index)

    def _choose_option(self, event: tk.Event[tk.Listbox] | None = None) -> str:
        if self.listbox is None:
            return "break"
        if event is not None and hasattr(event, "y"):
            index = self.listbox.nearest(event.y)
        elif self.listbox.curselection():
            index = int(self.listbox.curselection()[0])
        else:
            index = 0
        self.variable.set(self.values[index])
        self.command()
        self._close_popup()
        return "break"

    def _popup_focus_out(self, _event: tk.Event[tk.Misc]) -> None:
        def close_if_outside() -> None:
            if self.popup is not None and self.popup.focus_get() not in {self.popup, self.listbox}:
                self._close_popup()

        self.after(40, close_if_outside)

    def _close_popup(self, animate: bool = True) -> str:
        popup = self.popup
        if popup is None:
            return "break"
        self.popup = None
        self.listbox = None
        self._draw()
        try:
            height = popup.winfo_height()
            width = popup.winfo_width()
            x = popup.winfo_x()
            y = popup.winfo_y()
        except tk.TclError:
            return "break"

        def finish() -> None:
            try:
                popup.destroy()
            except tk.TclError:
                pass

        if not animate:
            finish()
            return "break"

        def collapse(frame_index: int = 0) -> None:
            if not popup.winfo_exists():
                return
            progress = min(1.0, (frame_index + 1) / 5)
            remaining = (1 - progress) ** 2
            popup.geometry(f"{width}x{max(1, round(height * remaining))}+{x}+{y}")
            try:
                popup.attributes("-alpha", remaining)
            except tk.TclError:
                pass
            if progress < 1:
                self.after(14, collapse, frame_index + 1)
            else:
                finish()

        collapse()
        self.focus_set()
        return "break"

    def configure(self, cnf: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        options = dict(cnf or {})
        options.update(kwargs)
        if "state" in options:
            state = options.pop("state")
            if state not in {"readonly", "disabled"}:
                raise tk.TclError(f'bad state "{state}": must be readonly or disabled')
            self.state = state
            if state == "disabled":
                self._close_popup(animate=False)
            self._sync_cursor()
        result = super().configure(**options)
        self._draw()
        return result

    config = configure

    def cget(self, key: str) -> Any:
        return self.state if key == "state" else super().cget(key)


class AnimatedSegmentedControl(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        options: tuple[tuple[str, str], ...],
        command: Any,
        *,
        width: int = 270,
        height: int = 36,
    ) -> None:
        super().__init__(
            parent,
            background=parent.cget("background"),
            borderwidth=0,
            highlightthickness=0,
            width=_ui(width),
            height=_ui(height),
            takefocus=True,
            cursor="hand2",
        )
        self.options = options
        self.command = command
        self.selected = options[0][0]
        self.hovered = -1
        self.pill_x = float(_ui(4))
        self.animation_job: str | None = None
        self.bind("<Configure>", self._configured)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._click)
        self.bind("<KeyPress-Left>", lambda _event: self._move(-1))
        self.bind("<KeyPress-Right>", lambda _event: self._move(1))
        self.bind("<KeyRelease-space>", lambda _event: self._activate(self._selected_index()))
        self.bind("<KeyRelease-Return>", lambda _event: self._activate(self._selected_index()))
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)

    def _segment_width(self) -> float:
        return max(1.0, (self.winfo_width() - _ui(8)) / len(self.options))

    def _target_x(self, index: int) -> float:
        return _ui(4) + index * self._segment_width()

    def _selected_index(self) -> int:
        return next(index for index, (value, _label) in enumerate(self.options) if value == self.selected)

    def _configured(self, _event: tk.Event[tk.Misc]) -> None:
        if self.animation_job is None:
            self.pill_x = self._target_x(self._selected_index())
        self._draw()

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        segment_width = self._segment_width()
        self.delete("segment")
        _begin_aa_draw(self)
        _draw_aa_round_rect(
            self,
            1,
            1,
            width - 1,
            height - 1,
            _corner(12),
            fill="#292D2A",
            outline="#7D929C" if self.focus_get() is self else "#4B524D",
            width=_ui(1),
            tags="segment",
        )
        if 0 <= self.hovered < len(self.options) and self.hovered != self._selected_index():
            x1 = self._target_x(self.hovered)
            _draw_aa_round_rect(
                self,
                round(x1 + _ui(2)),
                _ui(4),
                round(x1 + segment_width - _ui(2)),
                height - _ui(4),
                _corner(10),
                fill="#363B37",
                tags="segment",
            )
        _draw_aa_round_rect(
            self,
            round(self.pill_x + _ui(2)),
            _ui(3),
            round(self.pill_x + segment_width - _ui(2)),
            height - _ui(3),
            _corner(10),
            fill=COLORS["surface_blue"],
            tags="segment",
        )
        for index, (value, label) in enumerate(self.options):
            self.create_text(
                _ui(4) + (index + 0.5) * segment_width,
                height // 2,
                text=label,
                fill=COLORS["text"] if value == self.selected else "#D5DDD7",
                font=(FONT, 9, "bold"),
                tags="segment",
            )

    def _motion(self, event: tk.Event[tk.Misc]) -> None:
        self.hovered = min(len(self.options) - 1, max(0, int((event.x - _ui(4)) / self._segment_width())))
        self._draw()

    def _leave(self, _event: tk.Event[tk.Misc]) -> None:
        self.hovered = -1
        self._draw()

    def _click(self, event: tk.Event[tk.Misc]) -> None:
        self.focus_set()
        index = min(len(self.options) - 1, max(0, int((event.x - _ui(4)) / self._segment_width())))
        self._activate(index)

    def _move(self, direction: int) -> str:
        self._activate((self._selected_index() + direction) % len(self.options))
        return "break"

    def _activate(self, index: int) -> str:
        value = self.options[index][0]
        self.select(value)
        self.command(value)
        return "break"

    def select(self, value: str, *, animate: bool = True) -> None:
        values = [option[0] for option in self.options]
        if value not in values:
            raise ValueError(tr("error.segment_option", value=value))
        target = self._target_x(values.index(value))
        self.selected = value
        if self.animation_job is not None:
            self.after_cancel(self.animation_job)
            self.animation_job = None
        if not animate or abs(target - self.pill_x) < 1:
            self.pill_x = target
            self._draw()
            return
        start = self.pill_x

        def animate_step(frame_index: int = 0) -> None:
            progress = min(1.0, (frame_index + 1) / 9)
            eased = 1 - (1 - progress) ** 3
            self.pill_x = start + (target - start) * eased
            self._draw()
            if progress < 1:
                self.animation_job = self.after(16, animate_step, frame_index + 1)
            else:
                self.animation_job = None
                self.pill_x = self._target_x(values.index(value))
                self._draw()

        animate_step()

    def set_options(self, options: tuple[tuple[str, str], ...]) -> None:
        current = self.selected
        self.options = options
        if current not in {value for value, _label in options}:
            self.selected = options[0][0]
        self.pill_x = self._target_x(self._selected_index())
        self._draw()


class AnimatedProgressBar(tk.Canvas):
    def __init__(self, parent: tk.Misc, variable: tk.DoubleVar) -> None:
        super().__init__(
            parent,
            background=parent.cget("background"),
            borderwidth=0,
            highlightthickness=0,
            height=_ui(16),
        )
        self.variable = variable
        self.active = False
        self.phase = 0.0
        self.animation_job: str | None = None
        self.variable.trace_add("write", lambda *_: self._draw())
        self.bind("<Configure>", self._draw)

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = max(2, self.winfo_width() if self.winfo_ismapped() else self.winfo_reqwidth())
        height = max(2, self.winfo_height() if self.winfo_ismapped() else self.winfo_reqheight())
        top = max(1, height // 2 - _ui(6))
        bottom = min(height - 1, top + _ui(12))
        self.delete("progress")
        _begin_aa_draw(self)
        _draw_aa_round_rect(
            self,
            1,
            top,
            width - 1,
            bottom,
            _ui(6),
            fill=COLORS["surface_dark_soft"],
            outline="#424742",
            width=_ui(1),
            tags="progress",
        )
        value = min(100.0, max(0.0, float(self.variable.get())))
        fill_right = 1 + (width - 2) * value / 100
        if fill_right > 2:
            _draw_aa_round_rect(
                self,
                1,
                top,
                round(fill_right),
                bottom,
                _ui(6),
                fill=COLORS["accent"],
                tags="progress",
            )
        if self.active:
            limit = fill_right if value > 0 else width - 1
            pulse_width = min(float(_ui(52)), max(float(_ui(22)), limit * 0.22))
            pulse_left = -pulse_width + (limit + pulse_width) * self.phase
            pulse_right = min(limit, pulse_left + pulse_width)
            pulse_left = max(1.0, pulse_left)
            if pulse_right - pulse_left > 2:
                _draw_aa_round_rect(
                    self,
                    round(pulse_left),
                    top + _ui(1),
                    round(pulse_right),
                    bottom - _ui(1),
                    _ui(5),
                    fill="#F4FF9A",
                    tags="progress",
                )

    def set_active(self, active: bool) -> None:
        if active == self.active:
            return
        self.active = active
        if active:
            self._tick()
        elif self.animation_job is not None:
            self.after_cancel(self.animation_job)
            self.animation_job = None
            self._draw()

    def _tick(self) -> None:
        if not self.active:
            self.animation_job = None
            return
        self.phase = (self.phase + 0.045) % 1.0
        self._draw()
        self.animation_job = self.after(32, self._tick)

    def destroy(self) -> None:
        if self.animation_job is not None:
            self.after_cancel(self.animation_job)
            self.animation_job = None
        super().destroy()


def format_duration(seconds: float) -> str:
    total = max(0, round(float(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class FooterStatusIndicator(tk.Canvas):
    def __init__(self, parent: tk.Misc, variable: tk.StringVar) -> None:
        size = _ui(26)
        super().__init__(
            parent,
            background=parent.cget("background"),
            borderwidth=0,
            highlightthickness=0,
            width=size,
            height=size,
        )
        self.variable = variable
        self.photo: ImageTk.PhotoImage | None = None
        self.variable.trace_add("write", lambda *_: self._draw())
        self.bind("<Configure>", self._draw)

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        size = max(2, self.winfo_width(), self.winfo_reqwidth())
        factor = 4
        status = self.variable.get()
        success = status in translated_values("status.completed")
        failed = status in translated_values("status.failed") | translated_values("status.cancelled")
        color = COLORS["accent"] if success else ("#FF8A80" if failed else "#7E8982")
        image = Image.new("RGBA", (size * factor, size * factor), (0, 0, 0, 0))
        drawing = ImageDraw.Draw(image)
        inset = _ui(2) * factor
        stroke = max(factor, _ui(2) * factor)
        drawing.ellipse(
            (inset, inset, size * factor - inset - 1, size * factor - inset - 1),
            outline=color,
            width=stroke,
        )
        if success:
            drawing.line(
                (
                    _ui(7) * factor,
                    _ui(13) * factor,
                    _ui(11) * factor,
                    _ui(17) * factor,
                    _ui(19) * factor,
                    _ui(9) * factor,
                ),
                fill=color,
                width=stroke,
                joint="curve",
            )
        elif failed:
            drawing.line(
                (_ui(13) * factor, _ui(7) * factor, _ui(13) * factor, _ui(15) * factor),
                fill=color,
                width=stroke,
            )
            drawing.ellipse(
                (
                    _ui(12) * factor,
                    _ui(18) * factor,
                    _ui(14) * factor,
                    _ui(20) * factor,
                ),
                fill=color,
            )
        else:
            dot = _ui(3) * factor
            center = size * factor // 2
            drawing.ellipse((center - dot, center - dot, center + dot, center + dot), fill=color)
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image, master=self)
        self.delete("status-indicator")
        self.create_image(0, 0, image=self.photo, anchor="nw", tags="status-indicator")


class StatusDot(tk.Canvas):
    def __init__(self, parent: tk.Misc, ready: tk.BooleanVar) -> None:
        size = _ui(10)
        super().__init__(
            parent,
            background=parent.cget("background"),
            borderwidth=0,
            highlightthickness=0,
            width=size,
            height=size,
        )
        self.ready = ready
        self.photo: ImageTk.PhotoImage | None = None
        self.ready.trace_add("write", lambda *_: self._draw())
        self.bind("<Configure>", self._draw)

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        size = max(2, self.winfo_width(), self.winfo_reqwidth())
        factor = 4
        color = "#45C96B" if self.ready.get() else "#FF5F57"
        image = Image.new("RGBA", (size * factor, size * factor), (0, 0, 0, 0))
        drawing = ImageDraw.Draw(image)
        inset = factor
        drawing.ellipse(
            (inset, inset, size * factor - inset - 1, size * factor - inset - 1),
            fill=color,
            outline="#FFFFFF",
            width=factor,
        )
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image, master=self)
        self.delete("status-dot")
        self.create_image(0, 0, image=self.photo, anchor="nw", tags="status-dot")


def load_preview_image(path: Path) -> tuple[Image.Image, tuple[int, int]]:
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened)
        original_size = image.size
        image.thumbnail(PREVIEW_MAX_SIZE, Image.Resampling.LANCZOS)
        if "A" in image.getbands() or "transparency" in image.info:
            rgba = image.convert("RGBA")
            flattened = Image.new("RGB", rgba.size, COLORS["surface_dark_soft"])
            flattened.paste(rgba, mask=rgba.getchannel("A"))
            image = flattened
        else:
            image = image.convert("RGB")
        return image.copy(), original_size


def file_details(path: Path, dimensions: tuple[int, int]) -> str:
    size = path.stat().st_size
    size_text = (
        f"{size / (1024 * 1024):.1f} MB" if size >= 1024 * 1024 else f"{max(1, round(size / 1024))} KB"
    )
    file_type = path.suffix.removeprefix(".").upper() or tr("input.image_type")
    return f"{dimensions[0]} × {dimensions[1]}  ·  {file_type}  ·  {size_text}"


def compact_filename(name: str) -> str:
    return name if len(name) <= 24 else f"{name[:20]}…{Path(name).suffix}"


def validate_input_image_paths(paths: tuple[str, ...] | list[str]) -> tuple[Path | None, str]:
    if len(paths) != 1:
        return None, tr("input.only_one")
    source = Path(paths[0])
    if not source.is_file():
        return None, tr("input.not_found")
    if source.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        return None, tr("input.unsupported")
    return source, ""


def calculate_zoom_viewport(
    image_size: tuple[int, int],
    available_size: tuple[int, int],
    zoom: float,
    center: tuple[float, float],
) -> tuple[tuple[int, int, int, int], tuple[int, int], float, tuple[float, float]]:
    image_width, image_height = image_size
    available_width, available_height = (max(1, value) for value in available_size)
    zoom = min(4.0, max(1.0, zoom))
    fit_scale = min(available_width / image_width, available_height / image_height)
    render_scale = max(0.01, fit_scale * zoom)
    crop_width = max(1, min(image_width, round(available_width / render_scale)))
    crop_height = max(1, min(image_height, round(available_height / render_scale)))
    center_x = min(image_width - crop_width / 2, max(crop_width / 2, center[0] * image_width))
    center_y = min(image_height - crop_height / 2, max(crop_height / 2, center[1] * image_height))
    crop_left = min(image_width - crop_width, max(0, round(center_x - crop_width / 2)))
    crop_top = min(image_height - crop_height, max(0, round(center_y - crop_height / 2)))
    render_size = (
        min(available_width, max(1, round(crop_width * render_scale))),
        min(available_height, max(1, round(crop_height * render_scale))),
    )
    return (
        (crop_left, crop_top, crop_left + crop_width, crop_top + crop_height),
        render_size,
        render_scale,
        (center_x / image_width, center_y / image_height),
    )


class PreviewCard(tk.Canvas):
    def __init__(self, parent: tk.Misc, title: str, placeholder: str, *, zoomable: bool = False) -> None:
        super().__init__(
            parent,
            background=parent.cget("background"),
            borderwidth=0,
            highlightthickness=0,
            height=_ui(122),
            cursor="fleur" if zoomable else "arrow",
        )
        self.title = title
        self.placeholder = placeholder
        self.zoomable = zoomable
        self.image: Image.Image | None = None
        self.dimensions: tuple[int, int] | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.zoom = 1.0
        self.center = (0.5, 0.5)
        self.render_scale = 1.0
        self.drag_origin: tuple[int, int] | None = None
        self.bind("<Configure>", self._draw)
        if zoomable:
            self.bind("<MouseWheel>", self._wheel)
            self.bind("<ButtonPress-1>", self._press)
            self.bind("<B1-Motion>", self._drag)
            self.bind("<Double-Button-1>", lambda _event: self.reset_zoom())

    def clear(self, placeholder: str) -> None:
        self.placeholder = placeholder
        self.image = None
        self.dimensions = None
        self.photo = None
        self.reset_zoom(redraw=False)
        self._draw()

    def set_image(self, image: Image.Image, dimensions: tuple[int, int]) -> None:
        self.image = image
        self.dimensions = dimensions
        self.reset_zoom(redraw=False)
        self._draw()

    def set_text(self, title: str, placeholder: str | None = None) -> None:
        self.title = title
        if placeholder is not None and self.image is None:
            self.placeholder = placeholder
        self._draw()

    def reset_zoom(self, *, redraw: bool = True) -> str:
        self.zoom = 1.0
        self.center = (0.5, 0.5)
        if redraw:
            self._draw()
        return "break"

    def _wheel(self, event: tk.Event[tk.Misc]) -> str:
        if self.image is None:
            return "break"
        self.zoom = min(4.0, max(1.0, self.zoom * (1.2 if event.delta > 0 else 1 / 1.2)))
        if self.zoom <= 1.01:
            self.center = (0.5, 0.5)
        self._draw()
        return "break"

    def _press(self, event: tk.Event[tk.Misc]) -> str:
        self.drag_origin = (event.x, event.y)
        return "break"

    def _drag(self, event: tk.Event[tk.Misc]) -> str:
        if self.image is None or self.drag_origin is None or self.zoom <= 1.0:
            return "break"
        delta_x = event.x - self.drag_origin[0]
        delta_y = event.y - self.drag_origin[1]
        self.center = (
            self.center[0] - delta_x / self.render_scale / self.image.width,
            self.center[1] - delta_y / self.render_scale / self.image.height,
        )
        self.drag_origin = (event.x, event.y)
        self._draw()
        return "break"

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("preview")
        _begin_aa_draw(self)
        _draw_aa_round_rect(
            self,
            1,
            1,
            width - 1,
            height - 1,
            _corner(14),
            fill=COLORS["surface_dark_soft"],
            tags="preview",
        )
        self.create_text(
            _ui(12),
            _ui(10),
            anchor="nw",
            text=self.title,
            fill=COLORS["text_on_dark"],
            font=(FONT, 8, "bold"),
            tags="preview",
        )
        if self.dimensions:
            self.create_text(
                width - _ui(12),
                _ui(10),
                anchor="ne",
                text=f"{self.dimensions[0]}×{self.dimensions[1]}",
                fill=COLORS["text_muted_dark"],
                font=(FONT, 7),
                tags="preview",
            )

        left, top, right, bottom = _ui(10), _ui(30), width - _ui(10), height - _ui(10)
        _draw_aa_round_rect(
            self,
            left,
            top,
            right,
            bottom,
            _corner(10),
            fill="#171917",
            tags="preview",
        )
        if self.image:
            available = (max(1, right - left - _ui(8)), max(1, bottom - top - _ui(8)))
            crop_box, render_size, self.render_scale, self.center = calculate_zoom_viewport(
                self.image.size,
                available,
                self.zoom if self.zoomable else 1.0,
                self.center,
            )
            rendered = self.image.crop(crop_box).resize(render_size, Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(rendered)
            self.create_image(
                (left + right) // 2,
                (top + bottom) // 2,
                image=self.photo,
                anchor="center",
                tags="preview",
            )
            if self.zoomable and self.zoom > 1.01:
                self.create_text(
                    right - _ui(12),
                    bottom - _ui(12),
                    text=tr("preview.zoom_reset", percent=round(self.zoom * 100)),
                    anchor="se",
                    fill=COLORS["text_on_dark"],
                    font=(FONT, 8, "bold"),
                    tags="preview",
                )
        else:
            self.photo = None
            self.create_text(
                (left + right) // 2,
                (top + bottom) // 2,
                text=self.placeholder,
                fill=COLORS["text_muted_dark"],
                font=(FONT, 8),
                width=max(_ui(40), right - left - _ui(20)),
                justify="center",
                tags="preview",
            )


class ComparisonSlider(tk.Canvas):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(
            parent,
            background=parent.cget("background"),
            borderwidth=0,
            highlightthickness=0,
            takefocus=True,
            cursor="sb_h_double_arrow",
        )
        self.images: dict[str, Image.Image | None] = {"input": None, "output": None}
        self.position = 0.5
        self.photo: ImageTk.PhotoImage | None = None
        self.image_bounds: tuple[int, int, int, int] | None = None
        self.zoom = 1.0
        self.center = (0.5, 0.5)
        self.render_scale = 1.0
        self.pan_origin: tuple[int, int] | None = None
        self.bind("<Configure>", self._resize)
        self.bind("<Button-1>", self._slide)
        self.bind("<B1-Motion>", self._slide)
        self.bind("<ButtonPress-3>", self._start_pan)
        self.bind("<B3-Motion>", self._pan)
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Double-Button-1>", lambda _event: self.reset_zoom())
        self.bind("<Left>", self._nudge)
        self.bind("<Right>", self._nudge)
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)

    def set_image(self, kind: str, image: Image.Image | None) -> None:
        self.images[kind] = image
        self.reset_zoom(redraw=False)
        self._draw()

    def _resize(self, _event: tk.Event[tk.Misc]) -> None:
        self._draw()

    def reset_zoom(self, *, redraw: bool = True) -> str:
        self.zoom = 1.0
        self.center = (0.5, 0.5)
        if redraw:
            self._draw()
        return "break"

    def _wheel(self, event: tk.Event[tk.Misc]) -> str:
        if self.images["input"] is None or self.images["output"] is None:
            return "break"
        self.zoom = min(4.0, max(1.0, self.zoom * (1.2 if event.delta > 0 else 1 / 1.2)))
        if self.zoom <= 1.01:
            self.center = (0.5, 0.5)
        self.focus_set()
        self._draw()
        return "break"

    def _start_pan(self, event: tk.Event[tk.Misc]) -> str:
        self.pan_origin = (event.x, event.y)
        self.focus_set()
        return "break"

    def _pan(self, event: tk.Event[tk.Misc]) -> str:
        source = self.images["input"]
        if source is None or self.pan_origin is None or self.zoom <= 1.0:
            return "break"
        delta_x = event.x - self.pan_origin[0]
        delta_y = event.y - self.pan_origin[1]
        self.center = (
            self.center[0] - delta_x / self.render_scale / source.width,
            self.center[1] - delta_y / self.render_scale / source.height,
        )
        self.pan_origin = (event.x, event.y)
        self._draw()
        return "break"

    def _slide(self, event: tk.Event[tk.Misc]) -> str:
        if self.image_bounds:
            left, _, right, _ = self.image_bounds
            self.position = min(0.98, max(0.02, (event.x - left) / max(1, right - left)))
            self.focus_set()
            self._draw()
        return "break"

    def _nudge(self, event: tk.Event[tk.Misc]) -> str:
        self.position = min(0.98, max(0.02, self.position + (-0.03 if event.keysym == "Left" else 0.03)))
        self._draw()
        return "break"

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("comparison")
        _begin_aa_draw(self)
        _draw_aa_round_rect(
            self,
            1,
            1,
            width - 1,
            height - 1,
            _corner(14),
            fill=COLORS["surface_dark_soft"],
            outline=COLORS["accent"] if self.focus_get() is self else "",
            width=_ui(2),
            tags="comparison",
        )
        self.create_text(
            _ui(12),
            _ui(10),
            anchor="nw",
            text=tr("preview.input_title"),
            fill=COLORS["text_on_dark"],
            font=(FONT, 8, "bold"),
            tags="comparison",
        )
        self.create_text(
            width - _ui(12),
            _ui(10),
            anchor="ne",
            text=tr("preview.output_title"),
            fill=COLORS["text_on_dark"],
            font=(FONT, 8, "bold"),
            tags="comparison",
        )
        left, top, right, bottom = _ui(10), _ui(30), width - _ui(10), height - _ui(10)
        _draw_aa_round_rect(
            self,
            left,
            top,
            right,
            bottom,
            _corner(10),
            fill="#171917",
            tags="comparison",
        )
        source = self.images["input"]
        result = self.images["output"]
        if source is None or result is None:
            self.photo = None
            self.image_bounds = None
            self.create_text(
                width // 2,
                (top + bottom) // 2,
                text=tr("preview.compare_empty"),
                fill=COLORS["text_muted_dark"],
                font=(FONT, 8),
                tags="comparison",
            )
            return

        available = (max(1, right - left - _ui(8)), max(1, bottom - top - _ui(8)))
        normalized_result = result if result.size == source.size else result.resize(source.size, Image.Resampling.LANCZOS)
        crop_box, render_size, self.render_scale, self.center = calculate_zoom_viewport(
            source.size,
            available,
            self.zoom,
            self.center,
        )
        fitted_source = source.crop(crop_box).resize(render_size, Image.Resampling.LANCZOS)
        fitted_result = normalized_result.crop(crop_box).resize(render_size, Image.Resampling.LANCZOS)
        split = min(render_size[0] - 1, max(1, round(render_size[0] * self.position)))
        combined = fitted_result.copy()
        combined.paste(fitted_source.crop((0, 0, split, render_size[1])), (0, 0))
        self.photo = ImageTk.PhotoImage(combined)
        image_left = (width - render_size[0]) // 2
        image_top = top + (bottom - top - render_size[1]) // 2
        self.image_bounds = (
            image_left,
            image_top,
            image_left + render_size[0],
            image_top + render_size[1],
        )
        divider = image_left + split
        self.create_image(image_left, image_top, image=self.photo, anchor="nw", tags="comparison")
        self.create_line(
            divider,
            image_top,
            divider,
            image_top + render_size[1],
            fill=COLORS["accent"],
            width=_ui(2),
            tags="comparison",
        )
        handle_y = image_top + render_size[1] // 2
        _draw_aa_round_rect(
            self,
            divider - _ui(13),
            handle_y - _ui(13),
            divider + _ui(13),
            handle_y + _ui(13),
            _ui(13),
            fill=COLORS["accent"],
            outline=COLORS["text"],
            width=_ui(1),
            tags="comparison",
        )
        self.create_text(
            divider,
            handle_y,
            text="↔",
            fill=COLORS["text"],
            font=(FONT, 8, "bold"),
            tags="comparison",
        )
        if self.zoom > 1.01:
            self.create_text(
                image_left + render_size[0] - _ui(12),
                image_top + render_size[1] - _ui(12),
                text=tr("preview.zoom_reset", percent=round(self.zoom * 100)),
                anchor="se",
                fill=COLORS["text_on_dark"],
                font=(FONT, 8, "bold"),
                tags="comparison",
            )


class WorkerClient:
    def __init__(self, events: queue.Queue[dict[str, Any]], language: str) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(PROJECT_ROOT),
                "SEEDVR2_LANGUAGE": language,
            }
        )
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            [str(runtime_python()), "-B", "-u", "-m", "app.worker"],
            cwd=PROJECT_ROOT,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=flags,
        )
        self.events = events
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.process.stdout
        for line in self.process.stdout:
            try:
                self.events.put(json.loads(line))
            except json.JSONDecodeError:
                self.events.put({"event": "error", "message": tr("worker.protocol_broken"), "detail": line})
        code = self.process.poll()
        if code not in (None, 0):
            self.events.put({"event": "error", "message": tr("worker.exited", code=code)})

    def _read_stderr(self) -> None:
        assert self.process.stderr
        for line in self.process.stderr:
            self.events.put({"event": "worker_log", "message": line.rstrip()})

    def send(self, command: dict[str, Any]) -> None:
        if self.process.poll() is not None or not self.process.stdin:
            raise RuntimeError(tr("worker.not_running"))
        self.process.stdin.write(json.dumps(command, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            self.send({"command": "shutdown"})
            self.process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.language = load_language()
        set_language(self.language, persist=False)
        self.root.title(tr("app.title"))
        self.root.iconbitmap(default=str(PROJECT_ROOT / "assets" / "seedvr2.ico"))
        self.root.geometry(f"{_ui(1120)}x{_ui(780)}")
        self.root.minsize(_ui(1040), _ui(720))
        self.root.configure(background=COLORS["background"])
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.preview_events: queue.Queue[
            tuple[str, int, Image.Image | None, tuple[int, int] | None, str]
        ] = queue.Queue()
        self.preview_generations = {"input": 0, "output": 0}
        self.preview_cards: dict[str, PreviewCard] = {}
        self.preview_mode = "input"
        self.log_visible = False
        self._localized_labels: list[tuple[tk.Label, str]] = []
        self._localized_buttons: list[tuple[RoundedButton, str]] = []
        self._localized_variables: dict[int, tuple[tk.StringVar, str, dict[str, Any]]] = {}
        self.log_entries: list[tuple[str | None, dict[str, Any], str]] = []
        self.preview_placeholder_keys: dict[str, str | None] = {
            "input": "preview.input_empty",
            "output": "preview.output_empty",
        }
        self.open_buttons: list[RoundedButton] = []
        self.worker = WorkerClient(self.events, self.language)
        self.input_path = tk.StringVar()
        self.input_name = self._new_localized_var("input.none")
        self.input_meta = self._new_localized_var("input.formats")
        self.output_dir = tk.StringVar(
            value=os.environ.get("SEEDVR2_OUTPUT_DIR", str(Path.home() / "Pictures" / "SeedVR2 Upscaler"))
        )
        self.status = self._new_localized_var("status.worker_starting")
        self.detail = self._new_localized_var("detail.choose_image")
        self.progress = tk.DoubleVar(value=0)
        self.progress_percent = tk.StringVar(value="0%")
        self.footer_output_size = tk.StringVar(value="—")
        self.footer_elapsed = tk.StringVar(value="—")
        self.progress.trace_add("write", self._sync_progress_text)
        self.gpu_name = self._new_localized_var("status.gpu_detecting")
        self.gpu_ready = tk.BooleanVar(value=False)
        self.preview_hint = self._new_localized_var("preview.fit")
        self.scale_preset = tk.StringVar(value="4×")
        self.grid_preset = tk.StringVar(value=tr("preset.auto"))
        self.scale_status = self._new_localized_var("status.scale", scale=4)
        self.grid_status = self._new_localized_var("status.grid", grid="AUTO")
        self.size_hint = self._new_localized_var("size.default", profile="8–16GB")
        self.input_dimensions: tuple[int, int] | None = None
        self.memory_profile = "8–16GB"
        self.last_output: Path | None = None
        self.running = False
        self.preflight_complete = False
        self.path_controls_enabled = True
        self.path_controls: list[RoundedButton] = []
        self.preset_controls: list[AnimatedDropdown] = []
        self.input_click_targets: list[tk.Misc] = []
        self.input_thumbnail_photo: ImageTk.PhotoImage | None = None
        self._build()
        self.input_drop_zone.drop_target_register(DND_FILES)
        self.input_drop_zone.dnd_bind("<<Drop>>", self._drop_input_event)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(80, self._poll)

    def _new_localized_var(self, key: str, **values: Any) -> tk.StringVar:
        variable = tk.StringVar(value=tr(key, **values))
        self._localized_variables[id(variable)] = (variable, key, values)
        return variable

    def _set_localized(self, variable: tk.StringVar, key: str, **values: Any) -> None:
        self._localized_variables[id(variable)] = (variable, key, values)
        variable.set(tr(key, **values))

    def _set_raw(self, variable: tk.StringVar, value: object) -> None:
        self._localized_variables.pop(id(variable), None)
        variable.set(str(value))

    def _label(self, parent: tk.Misc, key: str | None = None, **options: Any) -> tk.Label:
        if key:
            options["text"] = tr(key)
        label = tk.Label(parent, **options)
        if key:
            self._localized_labels.append((label, key))
        return label

    def _change_language(self, language: str) -> None:
        if language == self.language:
            return
        self.language = set_language(language, persist=False)
        save_error: OSError | None = None
        try:
            set_language(language, persist=True)
        except OSError as error:
            save_error = error
        self._refresh_language()
        try:
            self.worker.send({"command": "set_language", "language": self.language})
        except (OSError, RuntimeError):
            pass
        if save_error:
            messagebox.showwarning(
                tr("dialog.settings_failed"),
                tr("dialog.settings_failed_message", error=save_error),
            )

    def _refresh_language(self) -> None:
        self.root.title(tr("app.title"))
        for label, key in self._localized_labels:
            if label.winfo_exists():
                label.configure(text=tr(key))
        for button, key in self._localized_buttons:
            if button.winfo_exists():
                button.configure(text=tr(key))
        for variable, key, values in list(self._localized_variables.values()):
            variable.set(tr(key, **values))
        auto_selected = self._selected_grid() is None
        current_grid = self.grid_preset.get()
        auto_label = tr("preset.auto")
        self.preset_controls[1].set_values(
            (auto_label, "3×3", "4×4", "5×5"),
            selected=auto_label if auto_selected else current_grid,
        )
        self.view_switch.set_options(
            (("input", tr("view.input")), ("compare", tr("view.compare")), ("output", tr("view.output")))
        )
        self.language_switch.select(self.language, animate=False)
        input_placeholder = self.preview_placeholder_keys["input"]
        output_placeholder = self.preview_placeholder_keys["output"]
        self.preview_cards["input"].set_text(
            tr("preview.input_title"),
            tr(input_placeholder) if input_placeholder else None,
        )
        self.preview_cards["output"].set_text(
            tr("preview.output_title"),
            tr(output_placeholder) if output_placeholder else None,
        )
        self.compare_slider._draw()
        self._preset_changed()
        self._set_preview_mode(self.preview_mode)
        self.log_button.configure(text=tr("action.hide_log" if self.log_visible else "action.view_log"))
        self._rebuild_log()

    def _sync_progress_text(self, *_args: Any) -> None:
        self.progress_percent.set(f"{round(min(100.0, max(0.0, self.progress.get())))}%")

    def _build(self) -> None:
        page = tk.Frame(self.root, background=COLORS["background"], padx=_ui(16), pady=_ui(14))
        page.pack(fill="both", expand=True)

        topbar = tk.Frame(page, background=COLORS["background"], height=_ui(42))
        topbar.pack(fill="x", pady=(0, _ui(12)))
        self._label(
            topbar,
            text="✦  SEEDVR2",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=(FONT, 11, "bold"),
        ).pack(side="left", padx=(_ui(2), _ui(12)))
        self._label(
            topbar,
            text="│",
            background=COLORS["background"],
            foreground=COLORS["border"],
            font=(FONT, 16),
        ).pack(side="left", padx=_ui(12))
        self._label(
            topbar,
            key="app.heading",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=(FONT, 18, "bold"),
        ).pack(side="left")

        badges = tk.Frame(topbar, background=COLORS["background"])
        badges.pack(side="right")
        self.gpu_badge = self._badge(badges, self.gpu_name, width=220, status=self.gpu_ready)
        self._badge(badges, self.scale_status, width=86)
        self._badge(badges, self.grid_status, width=102)
        for text, width in (("64 px", 68), ("LOCAL", 70)):
            self._badge(badges, text, width=width)
        self.language_switch = AnimatedSegmentedControl(
            badges,
            ((LANG_ZH, "中文"), (LANG_EN, "EN")),
            self._change_language,
            width=92,
            height=28,
        )
        self.language_switch.select(self.language, animate=False)
        self.language_switch.pack(side="left", padx=(_ui(6), 0))

        workspace = tk.Frame(page, background=COLORS["background"])
        workspace.pack(fill="both", expand=True)

        sidebar = RoundedPanel(
            workspace,
            color=COLORS["surface_dark"],
            radius=22,
            padding=14,
            width=300,
        )
        sidebar.pack(side="left", fill="y")
        task_panel = sidebar.content

        actions = tk.Frame(task_panel, background=COLORS["surface_dark"])
        actions.pack(side="bottom", fill="x", pady=(_ui(10), 0))
        self.preset_panel = tk.Frame(actions, background=COLORS["surface_dark"])
        self.preset_panel.pack(fill="x", pady=(0, _ui(10)))
        self.preset_panel.columnconfigure(0, weight=1, uniform="presets")
        self.preset_panel.columnconfigure(1, weight=1, uniform="presets")
        self._preset_selector(self.preset_panel, "preset.scale", self.scale_preset, ("2×", "4×", "6×", "8×"))
        self._preset_selector(
            self.preset_panel,
            "preset.grid",
            self.grid_preset,
            (tr("preset.auto"), "3×3", "4×4", "5×5"),
        )
        self.start_button = self._button(
            actions,
            tr("action.start", scale=4),
            self.start,
            background=COLORS["accent"],
            foreground=COLORS["text"],
            active_background="#CEEF00",
            state="disabled",
        )
        self.start_button.pack(fill="x", ipady=_ui(7))
        secondary_actions = tk.Frame(actions, background=COLORS["surface_dark"])
        secondary_actions.pack(fill="x", pady=(_ui(8), 0))
        self.stop_button = self._button(
            secondary_actions,
            tr("action.stop"),
            self.stop,
            background=COLORS["surface_dark_soft"],
            foreground=COLORS["text_on_dark"],
            active_background="#454944",
            state="disabled",
            text_key="action.stop",
        )
        self.stop_button.pack(side="left", fill="x", expand=True, ipady=_ui(3))
        self.open_button = self._button(
            secondary_actions,
            tr("action.open_output_short"),
            self.open_output,
            background=COLORS["surface_blue"],
            foreground=COLORS["text"],
            active_background="#9DB9C8",
            state="disabled",
            text_key="action.open_output_short",
        )
        self.open_button.pack(side="left", fill="x", expand=True, padx=(_ui(8), 0), ipady=_ui(3))
        self.open_buttons.append(self.open_button)

        task_header = tk.Frame(task_panel, background=COLORS["surface_dark"])
        task_header.pack(fill="x")
        self._label(
            task_header,
            key="task.new",
            background=COLORS["surface_dark"],
            foreground=COLORS["text_on_dark"],
            font=(FONT, 14, "bold"),
        ).pack(side="left")
        self._label(
            task_header,
            key="task.single",
            background=COLORS["surface_dark_soft"],
            foreground=COLORS["text_muted_dark"],
            font=(FONT, 8),
            padx=10,
            pady=4,
        ).pack(side="right")
        self._label(
            task_panel,
            key="task.subtitle",
            background=COLORS["surface_dark"],
            foreground=COLORS["text_muted_dark"],
            font=(FONT, 9),
        ).pack(anchor="w", pady=(_ui(4), _ui(16)))

        self._build_path_cards(task_panel)

        warning = RoundedPanel(
            task_panel,
            color="#36362C",
            radius=14,
            padding=10,
            height=66,
        )
        warning.pack(fill="x", pady=(_ui(8), 0))
        self._label(
            warning.content,
            text="!",
            background=COLORS["accent"],
            foreground=COLORS["text"],
            font=(FONT, 9, "bold"),
            width=2,
        ).pack(side="left")
        self._label(
            warning.content,
            key="task.warning",
            background="#36362C",
            foreground="#E5DCB5",
            font=(FONT, 8),
            justify="left",
            wraplength=230,
        ).pack(side="left", fill="x", expand=True, padx=(_ui(8), 0))

        preview_panel = RoundedPanel(
            workspace,
            color=COLORS["surface_dark"],
            radius=22,
            padding=12,
        )
        preview_panel.pack(side="left", fill="both", expand=True, padx=(_ui(12), 0))
        preview_panel.content.columnconfigure(0, weight=1)
        preview_panel.content.rowconfigure(1, weight=1)
        preview_panel.content.rowconfigure(2, weight=0)

        preview_toolbar = tk.Frame(
            preview_panel.content,
            background=COLORS["surface_dark_soft"],
            padx=_ui(8),
            pady=_ui(7),
        )
        preview_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, _ui(10)))
        self.view_switch = AnimatedSegmentedControl(
            preview_toolbar,
            (("input", tr("view.input")), ("compare", tr("view.compare")), ("output", tr("view.output"))),
            self._set_preview_mode,
        )
        self.view_switch.pack(side="left")
        self._label(
            preview_toolbar,
            textvariable=self.preview_hint,
            background=COLORS["surface_dark_soft"],
            foreground=COLORS["text_muted_dark"],
            font=(FONT, 8),
            padx=8,
        ).pack(side="right")

        preview_row = tk.Frame(preview_panel.content, background=COLORS["surface_dark"])
        preview_row.grid(row=1, column=0, sticky="nsew")
        preview_row.columnconfigure(0, weight=1)
        preview_row.columnconfigure(1, weight=1)
        preview_row.rowconfigure(0, weight=1)
        self.preview_cards["input"] = PreviewCard(
            preview_row,
            tr("preview.input_title"),
            tr("preview.input_empty"),
        )
        self.preview_cards["output"] = PreviewCard(
            preview_row,
            tr("preview.output_title"),
            tr("preview.output_empty"),
            zoomable=True,
        )
        self.compare_slider = ComparisonSlider(preview_row)
        self._set_preview_mode("input")

        self.log_panel = RoundedPanel(
            preview_panel.content,
            color=COLORS["surface_dark_soft"],
            radius=18,
            padding=10,
            height=118,
        )
        log_header = tk.Frame(self.log_panel.content, background=COLORS["surface_dark_soft"])
        log_header.pack(fill="x", pady=(0, 5))
        self._label(
            log_header,
            key="log.title",
            background=COLORS["surface_dark_soft"],
            foreground=COLORS["text_on_dark"],
            font=(FONT, 9, "bold"),
        ).pack(side="left")
        self._label(
            log_header,
            key="log.live",
            background=COLORS["surface_dark_soft"],
            foreground=COLORS["text_muted_dark"],
            font=(FONT, 8),
            padx=8,
            pady=2,
        ).pack(side="right")
        self.log = tk.Text(
            self.log_panel.content,
            height=3,
            state="disabled",
            wrap="word",
            background=COLORS["surface_dark_soft"],
            foreground="#DCE4DD",
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=8,
            font=("Consolas", 8),
        )
        self.log.pack(fill="both", expand=True)

        self.footer = RoundedPanel(page, color=COLORS["surface_dark"], radius=18, padding=10, height=68)
        self.footer.pack(fill="x", pady=(_ui(10), 0))
        self.footer.content.columnconfigure(1, weight=1)
        self.footer.content.rowconfigure(0, weight=1)
        status_group = tk.Frame(self.footer.content, background=COLORS["surface_dark"])
        status_group.grid(row=0, column=0, sticky="w", padx=(_ui(2), _ui(18)))
        self.footer_status_indicator = FooterStatusIndicator(status_group, self.status)
        self.footer_status_indicator.pack(side="left", padx=(0, _ui(8)))
        self._label(
            status_group,
            textvariable=self.status,
            background=COLORS["surface_dark"],
            foreground=COLORS["text_on_dark"],
            font=(FONT, 9, "bold"),
        ).pack(side="left")
        self.progress_bar = AnimatedProgressBar(self.footer.content, self.progress)
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=(0, _ui(10)))
        self._label(
            self.footer.content,
            textvariable=self.progress_percent,
            background=COLORS["surface_dark"],
            foreground=COLORS["text_on_dark"],
            font=(FONT, 9, "bold"),
            width=4,
            anchor="e",
        ).grid(row=0, column=2, sticky="e", padx=(0, _ui(14)))
        self._footer_separator(self.footer.content, 3)
        self._footer_metric(self.footer.content, 4, "footer.output_size", self.footer_output_size, width=13)
        self._footer_separator(self.footer.content, 5)
        self._footer_metric(self.footer.content, 6, "footer.elapsed", self.footer_elapsed, width=10)
        self._footer_separator(self.footer.content, 7)
        self.log_button = self._button(
            self.footer.content,
            tr("action.view_log"),
            self.toggle_log,
            background=COLORS["surface_dark"],
            foreground=COLORS["text_on_dark"],
            active_background="#454944",
            border_color="#4B524D",
            border_width=1,
            icon="log",
        )
        self.log_button.grid(row=0, column=8, sticky="ew", padx=(0, _ui(8)), ipady=_ui(3))
        self.footer_open_button = self._button(
            self.footer.content,
            tr("action.open_output"),
            self.open_output,
            background=COLORS["surface_blue"],
            foreground=COLORS["text"],
            active_background="#9DB9C8",
            state="disabled",
            icon="folder",
            text_key="action.open_output",
        )
        self.footer_open_button.grid(row=0, column=9, sticky="ew", ipady=_ui(3))
        self.open_buttons.append(self.footer_open_button)

    def _button(
        self,
        parent: tk.Misc,
        text: str,
        command: Any,
        *,
        background: str,
        foreground: str,
        active_background: str,
        state: str = "normal",
        border_color: str = "",
        border_width: int = 0,
        icon: str = "",
        text_key: str = "",
    ) -> RoundedButton:
        button = RoundedButton(
            parent,
            text,
            command,
            background=background,
            foreground=foreground,
            active_background=active_background,
            state=state,
            border_color=border_color,
            border_width=border_width,
            icon=icon,
        )
        if text_key:
            self._localized_buttons.append((button, text_key))
        return button

    def _footer_separator(self, parent: tk.Misc, column: int) -> None:
        tk.Frame(parent, background="#414642", width=_ui(1)).grid(
            row=0,
            column=column,
            sticky="ns",
            padx=(0, _ui(14)),
        )

    def _footer_metric(
        self,
        parent: tk.Misc,
        column: int,
        label_key: str,
        value: tk.StringVar,
        *,
        width: int,
    ) -> None:
        group = tk.Frame(parent, background=COLORS["surface_dark"], width=_ui(width * 7))
        group.grid(row=0, column=column, sticky="w", padx=(0, _ui(14)))
        self._label(
            group,
            key=label_key,
            background=COLORS["surface_dark"],
            foreground=COLORS["text_muted_dark"],
            font=(FONT, 7),
            anchor="w",
        ).pack(anchor="w")
        self._label(
            group,
            textvariable=value,
            background=COLORS["surface_dark"],
            foreground=COLORS["text_on_dark"],
            font=(FONT, 9, "bold"),
            width=width,
            anchor="w",
        ).pack(anchor="w")

    def _badge(
        self,
        parent: tk.Misc,
        value: str | tk.StringVar,
        *,
        width: int,
        status: tk.BooleanVar | None = None,
    ) -> RoundedPanel:
        badge = RoundedPanel(
            parent,
            color=COLORS["surface_soft"],
            radius=13,
            padding=0,
            width=width,
            height=28,
        )
        badge.pack(side="left", padx=(_ui(6), 0))
        options = {"textvariable": value} if isinstance(value, tk.StringVar) else {"text": value}
        label_parent: tk.Misc = badge.content
        if status is not None:
            body = tk.Frame(badge.content, background=COLORS["surface_soft"])
            body.pack(fill="both", expand=True)
            status_dot = StatusDot(body, status)
            status_dot.pack(side="left", padx=(_ui(10), _ui(6)))
            badge.status_dot = status_dot  # type: ignore[attr-defined]
            label_parent = body
        self._label(
            label_parent,
            **options,
            background=COLORS["surface_soft"],
            foreground=COLORS["text"],
            font=(FONT, 8, "bold"),
        ).pack(side="left" if status is not None else "top", fill="both", expand=True)
        return badge

    def _preset_selector(
        self,
        parent: tk.Misc,
        label_key: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
    ) -> None:
        panel = RoundedPanel(
            parent,
            color="#393D39",
            radius=11,
            padding=7,
            height=62,
        )
        column = len(self.preset_controls)
        panel.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=(0, _ui(4)) if column == 0 else (_ui(4), 0),
        )
        self._label(
            panel.content,
            key=label_key,
            background="#393D39",
            foreground=COLORS["text_muted_dark"],
            font=(FONT, 7),
        ).pack(anchor="w", pady=(0, _ui(3)))
        control = AnimatedDropdown(
            panel.content,
            variable,
            values,
            self._preset_changed,
        )
        control.pack(fill="x")
        self.preset_controls.append(control)

    def _set_preview_mode(self, mode: str) -> None:
        if mode not in {"input", "compare", "output"}:
            raise ValueError(tr("error.preview_mode", mode=mode))
        self.preview_mode = mode
        for card in self.preview_cards.values():
            card.grid_forget()
        self.compare_slider.grid_forget()
        if mode == "input":
            self.preview_cards["input"].grid(row=0, column=0, columnspan=2, sticky="nsew")
        elif mode == "output":
            self.preview_cards["output"].grid(row=0, column=0, columnspan=2, sticky="nsew")
        else:
            self.compare_slider.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.view_switch.select(mode)
        self._set_localized(
            self.preview_hint,
            {"input": "preview.fit", "compare": "preview.compare_help", "output": "preview.output_help"}[mode],
        )

    def toggle_log(self) -> None:
        self._set_log_visible(not self.log_visible)

    def _set_log_visible(self, visible: bool) -> None:
        if visible == self.log_visible:
            return
        self.log_visible = visible
        if visible:
            self.log_panel.grid(row=2, column=0, sticky="ew", pady=(_ui(10), 0))
        else:
            self.log_panel.grid_remove()
        self.log_button.configure(text=tr("action.hide_log" if visible else "action.view_log"))

    def _set_open_controls(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.open_buttons:
            button.configure(state=state)

    def _build_path_cards(self, parent: tk.Misc) -> None:
        input_card = RoundedPanel(
            parent,
            color="#2E312E",
            radius=14,
            padding=10,
            height=166,
        )
        input_card.pack(fill="x", pady=(0, _ui(8)))
        self.input_drop_zone = input_card
        self._label(
            input_card.content,
            key="input.label",
            background="#2E312E",
            foreground=COLORS["text_on_dark"],
            font=(FONT, 9, "bold"),
        ).pack(anchor="w", pady=(0, _ui(5)))
        input_summary = RoundedPanel(
            input_card.content,
            color="#393D39",
            radius=11,
            padding=6,
            height=54,
        )
        input_summary.pack(fill="x", pady=(0, _ui(6)))
        thumbnail = RoundedPanel(
            input_summary.content,
            color="#202320",
            radius=8,
            padding=0,
            width=50,
            height=42,
        )
        thumbnail.pack(side="left")
        self.input_thumbnail = tk.Label(
            thumbnail.content,
            text="＋",
            background="#202320",
            foreground=COLORS["text_muted_dark"],
            font=(FONT, 15),
        )
        self.input_thumbnail.pack(fill="both", expand=True)
        self.input_click_targets = [thumbnail, thumbnail.content, self.input_thumbnail]
        for target in self.input_click_targets:
            target.configure(cursor="hand2")
            target.bind("<Button-1>", self._choose_input_from_thumbnail)
        input_text = tk.Frame(input_summary.content, background="#393D39")
        input_text.pack(side="left", fill="both", expand=True, padx=(_ui(9), 0))
        tk.Label(
            input_text,
            textvariable=self.input_name,
            background="#393D39",
            foreground=COLORS["text_on_dark"],
            font=(FONT, 8, "bold"),
            anchor="w",
            width=25,
        ).pack(fill="x")
        tk.Label(
            input_text,
            textvariable=self.input_meta,
            background="#393D39",
            foreground=COLORS["text_muted_dark"],
            font=(FONT, 7),
            anchor="w",
            width=29,
        ).pack(fill="x", pady=(_ui(2), 0))
        choose_input_button = self._button(
            input_card.content,
            tr("action.choose_image"),
            self.choose_input,
            background="#393D39",
            foreground=COLORS["text_on_dark"],
            active_background="#4A4F4A",
            text_key="action.choose_image",
        )
        choose_input_button.pack(fill="x", ipady=_ui(2))
        self._label(
            input_card.content,
            textvariable=self.size_hint,
            background="#2E312E",
            foreground="#DCCB93",
            font=(FONT, 7),
            anchor="w",
            justify="left",
            wraplength=_ui(260),
        ).pack(fill="x", pady=(_ui(5), 0))

        output_card = RoundedPanel(
            parent,
            color="#2E312E",
            radius=14,
            padding=10,
            height=104,
        )
        output_card.pack(fill="x")
        self._label(
            output_card.content,
            key="output.label",
            background="#2E312E",
            foreground=COLORS["text_on_dark"],
            font=(FONT, 9, "bold"),
        ).pack(anchor="w", pady=(0, _ui(4)))
        output_path = tk.Frame(output_card.content, background="#2E312E")
        output_path.pack(fill="x", pady=(0, _ui(5)))
        self._label(
            output_path,
            text="▱",
            background="#2E312E",
            foreground=COLORS["text_muted_dark"],
            font=(FONT, 12),
        ).pack(side="left", padx=(_ui(1), _ui(7)))
        self._label(
            output_path,
            textvariable=self.output_dir,
            background="#2E312E",
            foreground=COLORS["text_on_dark"],
            font=(FONT, 7),
            anchor="w",
            width=34,
        ).pack(side="left", fill="x", expand=True)
        choose_output_button = self._button(
            output_card.content,
            tr("action.change"),
            self.choose_output,
            background="#393D39",
            foreground=COLORS["text_on_dark"],
            active_background="#4A4F4A",
            text_key="action.change",
        )
        choose_output_button.pack(fill="x", ipady=_ui(2))
        self.path_controls.extend([choose_input_button, choose_output_button])

    def _set_path_controls(self, enabled: bool) -> None:
        self.path_controls_enabled = enabled
        state = "normal" if enabled else "disabled"
        for widget in self.path_controls:
            widget.configure(state=state)
        for widget in self.preset_controls:
            widget.configure(state="readonly" if enabled else "disabled")
        for widget in self.input_click_targets:
            widget.configure(cursor="hand2" if enabled else "arrow")

    def _selected_scale(self) -> int:
        return int(self.scale_preset.get().removesuffix("×"))

    def _selected_grid(self) -> int | None:
        value = self.grid_preset.get()
        return None if value in translated_values("preset.auto") else int(value.split("×", 1)[0])

    def _preset_changed(self, _event: tk.Event | None = None) -> None:
        scale = self._selected_scale()
        grid = self.grid_preset.get()
        self._set_localized(self.scale_status, "status.scale", scale=scale)
        self._set_localized(self.grid_status, "status.grid", grid="AUTO" if self._selected_grid() is None else grid)
        self.start_button.configure(text=tr("action.start", scale=scale))
        if scale >= 6:
            key = "size.high"
            values: dict[str, Any] = {}
        else:
            key = "size.default"
            values = {"profile": self.memory_profile}
        hint = tr(key, **values)
        if self._selected_grid() is not None:
            hint += tr("size.manual")
            self._set_raw(self.size_hint, hint)
        else:
            self._set_localized(self.size_hint, key, **values)

    def choose_input(self) -> None:
        if not self.path_controls_enabled:
            return
        path = filedialog.askopenfilename(
            title=tr("dialog.choose_image"),
            filetypes=[
                (tr("dialog.image_files"), "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
                (tr("dialog.all_files"), "*.*"),
            ],
        )
        if path:
            self._accept_input_paths((path,))

    def _choose_input_from_thumbnail(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.choose_input()
        return "break"

    def _accept_dropped_input(self, paths: tuple[str, ...]) -> None:
        if not self.path_controls_enabled:
            messagebox.showwarning(tr("dialog.change_blocked_title"), tr("dialog.change_blocked"))
            return
        self._accept_input_paths(paths)

    def _drop_input_event(self, event: Any) -> str:
        self._accept_dropped_input(tuple(self.root.tk.splitlist(event.data)))
        return str(event.action)

    def _accept_input_paths(self, paths: tuple[str, ...]) -> None:
        source, error = validate_input_image_paths(paths)
        if source is None:
            messagebox.showwarning(tr("dialog.add_failed"), error)
            return
        self.input_dimensions = None
        self.input_path.set(str(source))
        self._set_raw(self.input_name, compact_filename(source.name))
        self._set_localized(self.input_meta, "input.loading_info")
        self.input_thumbnail_photo = None
        self.input_thumbnail.configure(image="", text="…")
        self._set_raw(self.detail, source.name)
        self.last_output = None
        self._set_open_controls(False)
        self._request_preview("input", source, "preview.loading_input")
        self._request_preview("output", None, "preview.output_empty")
        self._set_preview_mode("input")

    def choose_output(self) -> None:
        path = filedialog.askdirectory(title=tr("dialog.choose_output"))
        if path:
            self.output_dir.set(path)

    def start(self) -> None:
        source = Path(self.input_path.get())
        output = Path(self.output_dir.get())
        if not source.is_file():
            messagebox.showerror(tr("dialog.start_failed"), tr("dialog.select_valid"))
            return
        scale = self._selected_scale()
        grid = self._selected_grid()
        if scale >= 6:
            output_size = (
                tr(
                    "dialog.high_scale_output",
                    width=self.input_dimensions[0] * scale,
                    height=self.input_dimensions[1] * scale,
                )
                if self.input_dimensions
                else ""
            )
            if not messagebox.askokcancel(
                tr("dialog.high_scale_title"),
                tr("dialog.high_scale", scale=scale, output_size=output_size),
                icon="warning",
            ):
                return
        try:
            output.mkdir(parents=True, exist_ok=True)
            self.worker.send(
                {
                    "command": "run",
                    "source": str(source),
                    "outputDir": str(output),
                    "scale": scale,
                    "grid": "auto" if grid is None else grid,
                }
            )
        except Exception as error:
            messagebox.showerror(tr("dialog.start_failed"), str(error))
            return
        self.running = True
        self.last_output = None
        self.progress.set(0)
        self.footer_output_size.set("—")
        self.footer_elapsed.set("—")
        self.progress_bar.set_active(True)
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._set_open_controls(False)
        self._set_path_controls(False)
        self._request_preview("input", source, "preview.loading_input")
        self._request_preview("output", None, "preview.processing")
        self._set_preview_mode("input")

    def stop(self) -> None:
        self.worker.send({"command": "cancel"})
        self.stop_button.configure(state="disabled")
        self._set_localized(self.status, "status.stopping")
        self._set_localized(self.detail, "detail.stopping")

    def open_output(self) -> None:
        target = self.last_output.parent if self.last_output else Path(self.output_dir.get())
        if target.is_dir():
            os.startfile(target)

    def _append_log(
        self,
        text: str = "",
        *,
        key: str | None = None,
        values: dict[str, Any] | None = None,
    ) -> None:
        values = values or {}
        rendered = tr(key, **values) if key else text
        self.log_entries.append((key, values, text))
        self.log.configure(state="normal")
        self.log.insert("end", rendered + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _rebuild_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        for key, values, text in self.log_entries:
            self.log.insert("end", (tr(key, **values) if key else text) + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    @staticmethod
    def _event_message(event: dict[str, Any]) -> tuple[str, str | None, dict[str, Any]]:
        key = event.get("messageKey")
        values = event.get("messageArgs")
        if isinstance(key, str) and isinstance(values, dict):
            return tr(key, **values), key, values
        return str(event.get("message", "")), None, {}

    def _request_preview(self, kind: str, path: Path | None, placeholder_key: str) -> None:
        self.preview_generations[kind] += 1
        generation = self.preview_generations[kind]
        self.preview_placeholder_keys[kind] = placeholder_key
        self.preview_cards[kind].clear(tr(placeholder_key))
        self.compare_slider.set_image(kind, None)
        if path is None:
            return
        threading.Thread(
            target=self._load_preview,
            args=(kind, generation, path),
            daemon=True,
        ).start()

    def _load_preview(self, kind: str, generation: int, path: Path) -> None:
        try:
            image, dimensions = load_preview_image(path)
            self.preview_events.put((kind, generation, image, dimensions, ""))
        except Exception as error:
            self.preview_events.put((kind, generation, None, None, str(error)))

    def _poll_previews(self) -> None:
        while True:
            try:
                kind, generation, image, dimensions, error = self.preview_events.get_nowait()
            except queue.Empty:
                break
            if generation != self.preview_generations[kind]:
                continue
            if image is None or dimensions is None:
                self.preview_placeholder_keys[kind] = None
                self.preview_cards[kind].clear(
                    tr("preview.error", error=error) if error else tr("preview.unavailable")
                )
                self.compare_slider.set_image(kind, None)
                if kind == "input":
                    self._set_localized(self.input_meta, "input.read_failed")
                    self.input_thumbnail.configure(image="", text="!")
            else:
                self.preview_cards[kind].set_image(image, dimensions)
                self.compare_slider.set_image(kind, image)
                if kind == "input":
                    self.input_dimensions = dimensions
                    thumbnail = image.copy()
                    thumbnail.thumbnail((48, 40), Image.Resampling.LANCZOS)
                    self.input_thumbnail_photo = ImageTk.PhotoImage(thumbnail)
                    self.input_thumbnail.configure(image=self.input_thumbnail_photo, text="")
                    try:
                        self._set_raw(self.input_meta, file_details(Path(self.input_path.get()), dimensions))
                    except OSError:
                        self._set_raw(self.input_meta, f"{dimensions[0]} × {dimensions[1]}")

    def _poll(self) -> None:
        while True:
            try:
                self._handle(self.events.get_nowait())
            except queue.Empty:
                break
        self._poll_previews()
        self.root.after(80, self._poll)

    def _handle(self, event: dict[str, Any]) -> None:
        name = event.get("event")
        message, message_key, message_values = self._event_message(event)
        if name == "ready":
            self._set_localized(self.status, "status.checking_cuda")
            self.worker.send({"command": "self_check", "withCuda": True})
        elif name == "self_check":
            system = event.get("result", {}).get("system", {})
            self._set_localized(self.status, "status.worker_ready")
            gpu = system.get("gpu", "CUDA")
            self._set_localized(
                self.gpu_name,
                "status.gpu_ready",
                gpu=str(gpu).replace("NVIDIA GeForce ", ""),
            )
            self.gpu_ready.set(True)
            self.memory_profile = str(system.get("memoryProfile", "8–16GB"))
            self._preset_changed()
            self._set_localized(self.detail, "detail.ready", profile=self.memory_profile)
            self.preflight_complete = True
            self.start_button.configure(state="normal")
        elif name in {"status", "progress", "model_ready", "system_ready", "cancel_requested"}:
            if message_key:
                self._set_localized(self.status, message_key, **message_values)
            else:
                self._set_raw(self.status, message)
            self.progress.set(float(event.get("progress", self.progress.get() / 100)) * 100)
            if name == "progress":
                self._set_localized(
                    self.detail,
                    "detail.current_tile",
                    current=event.get("current"),
                    total=event.get("total"),
                )
            if name == "status" and event.get("stage") == "assemble":
                self.stop_button.configure(state="disabled")
            self._append_log(message, key=message_key, values=message_values)
        elif name == "completed":
            self.running = False
            self.progress_bar.set_active(False)
            self.last_output = Path(event["output"])
            metrics = event["metrics"]
            self._set_localized(self.status, "status.completed")
            self.footer_output_size.set(f"{metrics['outputSize'][0]} × {metrics['outputSize'][1]}")
            self.footer_elapsed.set(format_duration(metrics["timings"]["wallSeconds"]))
            self._set_localized(
                self.detail,
                "detail.completed",
                scale=metrics["scale"],
                columns=metrics["tiles"][0],
                rows=metrics["tiles"][1],
                width=metrics["outputSize"][0],
                height=metrics["outputSize"][1],
                seconds=metrics["timings"]["wallSeconds"],
                mebibytes=metrics["outputBytes"] / 1024 / 1024,
                profile=metrics["memoryProfile"],
                gibibytes=metrics["memory"]["peakReservedBytes"] / 1024**3,
            )
            self.progress.set(100)
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self._set_open_controls(True)
            self._set_path_controls(True)
            self._append_log(str(self.last_output))
            self._request_preview("output", self.last_output, "preview.loading_output")
            self._set_preview_mode("compare")
        elif name == "cancelled":
            self.running = False
            self.progress_bar.set_active(False)
            self._set_localized(self.status, "status.cancelled")
            if message_key:
                self._set_localized(self.detail, message_key, **message_values)
            else:
                self._set_raw(self.detail, message)
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self._set_path_controls(True)
            self._request_preview("output", None, "preview.no_result")
            self._set_preview_mode("input")
        elif name == "error":
            was_running = self.running
            self.running = False
            self.progress_bar.set_active(False)
            self._set_localized(self.status, "status.failed")
            if not self.preflight_complete:
                self.gpu_ready.set(False)
                self._set_localized(self.gpu_name, "status.gpu_unavailable")
            self._set_raw(self.detail, message)
            self.start_button.configure(state="normal" if self.preflight_complete else "disabled")
            self.stop_button.configure(state="disabled")
            self._set_path_controls(True)
            self._append_log(message)
            if event.get("log"):
                self._append_log(key="log.path", values={"path": event["log"]})
            if was_running:
                self._request_preview("output", None, "preview.no_result")
                self._set_preview_mode("input")
            self._set_log_visible(True)
            messagebox.showerror(tr("dialog.processing_failed"), message)
        elif name == "worker_log" and message:
            self._append_log(message)

    def close(self) -> None:
        self.progress_bar.set_active(False)
        self.worker.close()
        self.root.destroy()


def main() -> None:
    from .qt_main_window import main as qt_main

    qt_main()


if __name__ == "__main__":
    main()
