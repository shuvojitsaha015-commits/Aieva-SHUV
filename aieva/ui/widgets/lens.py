"""The lens of the board - the Google Lens of the smart board.

The teacher writes something on the board and **taps** it. A window opens
with the picture of the board, the teacher drags a rectangle over the
writing, and Aieva reads it, solves it and shows the answer.

Two widgets live here:

* :class:`LensOverlay` - the picture of the board with the draggable area
  (the teacher picks what should be read);
* :class:`LensResult` - the popup with the reading, the answer, the steps
  and the graph.

Both are pure Kivy - the work happens in the background (the OCR worker and
the math core), never on the UI thread.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image as KivyImage
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from aieva.ui import theme

#: The smallest area the teacher may pick (in the pixels of the picture).
MIN_SIZE = 24


def _button(text: str, color: tuple[float, float, float, float]) -> Button:
    """A button of the board (the rules of the smart board are kept)."""
    return Button(
        text=text,
        size_hint_y=None,
        height=dp(theme.BUTTON_HEIGHT_DP),
        background_normal="",
        background_color=color,
        color=theme.TEXT,
        font_size=theme.sp_size(16),
    )


def _label(text: str, size: float, color: tuple[float, float, float, float]) -> Label:
    """A label that wraps its text."""
    widget = Label(
        text=text,
        size_hint_y=None,
        font_size=theme.sp_size(size),
        color=color,
        halign="left",
        valign="top",
    )
    widget.bind(size=lambda w, _v: setattr(w, "text_size", (w.width, None)))
    widget.bind(texture_size=lambda w, value: setattr(w, "height", value[1]))
    return widget


class LensOverlay(FloatLayout):
    """The picture of the board - the teacher picks the area to read."""

    #: Called with the area in the pixels of the picture.
    on_confirm: Callable[[tuple[int, int, int, int]], None] | None = None
    #: Called when the teacher steps back.
    on_cancel: Callable[[], None] | None = None

    def __init__(self, image: Any = None, **kwargs: Any) -> None:
        kwargs.setdefault("size_hint", (1, 1))
        super().__init__(**kwargs)
        self.image = image
        self.start: tuple[float, float] | None = None
        self.current: tuple[float, float] | None = None
        self._picture_path: str = ""
        self._picture_size: tuple[int, int] = (0, 0)
        self._build()

    # ------------------------------------------------------------------ ui
    def _build(self) -> None:
        with self.canvas.before:
            Color(0, 0, 0, 0.82)
            self._background = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            Color(theme.ACCENT[0], theme.ACCENT[1], theme.ACCENT[2], 1)
            self._border = Line(rectangle=(0, 0, 0, 0), width=2.0)
        self.bind(pos=self._redraw, size=self._redraw)

        self.picture = KivyImage(
            size_hint=(None, None),
            allow_stretch=True,
            keep_ratio=True,
            pos_hint={"center_x": 0.5, "center_y": 0.56},
        )
        self.add_widget(self.picture)

        heading = _label(
            "Drag over the writing you want to read, then tap Scan.",
            16,
            theme.TEXT,
        )
        heading.size_hint_y = None
        heading.height = dp(28)
        heading.pos_hint = {"center_x": 0.5, "top": 0.96}
        self.add_widget(heading)

        actions = BoxLayout(
            orientation="horizontal",
            size_hint=(0.5, None),
            height=dp(theme.BUTTON_HEIGHT_DP),
            pos_hint={"center_x": 0.5, "center_y": 0.06},
            spacing=dp(theme.GAP_DP),
        )
        cancel = _button("Cancel", theme.SURFACE_ALT)
        cancel.bind(on_release=lambda _b: self._cancel())
        scan = _button("Scan this area", theme.PRIMARY)
        scan.bind(on_release=lambda _b: self._confirm())
        actions.add_widget(cancel)
        actions.add_widget(scan)
        self.add_widget(actions)

    def set_image(self, image: Any) -> None:
        """Show the picture of the board."""
        self.image = image
        self._picture_path = ""
        try:
            if image is not None:
                with tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False, prefix="aieva-lens-"
                ) as handle:
                    path = Path(handle.name)
                image.save(path, format="PNG")
                self._picture_path = str(path)
                self._picture_size = image.size
                self.picture.source = self._picture_path
        except Exception:  # noqa: BLE001 - the picture is a nice to have
            self._picture_path = ""

    # --------------------------------------------------------------- touch
    def on_touch_down(self, touch: Any) -> bool:
        if not self.collide_point(*touch.pos):
            return False
        if not self.picture.collide_point(*touch.pos):
            return False
        self.start = touch.pos
        self.current = touch.pos
        self._redraw()
        return True

    def on_touch_move(self, touch: Any) -> bool:
        if self.start is None:
            return False
        self.current = touch.pos
        self._redraw()
        return True

    def on_touch_up(self, touch: Any) -> bool:
        if self.start is None:
            return False
        self.current = touch.pos
        self._redraw()
        return True

    # ----------------------------------------------------------------- api
    def region(self) -> tuple[int, int, int, int]:
        """The picked area in the pixels of the picture."""
        if self.start is None or self.current is None:
            return (0, 0, 0, 0)
        width, height = self.picture.size
        source_width, source_height = self._picture_size or (width, height)
        if width <= 0 or height <= 0:
            return (0, 0, 0, 0)
        scale_x = source_width / width
        scale_y = source_height / height
        left = int(min(self.start[0], self.current[0]))
        right = int(max(self.start[0], self.current[0]))
        top = int(min(self.start[1], self.current[1]))
        bottom = int(max(self.start[1], self.current[1]))
        # the picture keeps its ratio, so the empty space is on one side
        offset_x = self.picture.center_x - width / 2
        offset_y = self.picture.center_y - height / 2
        left = int(max(0, (left - offset_x) * scale_x))
        right = int(min(source_width, (right - offset_x) * scale_x))
        top = int(max(0, (top - offset_y) * scale_y))
        bottom = int(min(source_height, (bottom - offset_y) * scale_y))
        return (left, top, right, bottom)

    def _confirm(self) -> None:
        region = self.region()
        if region[2] - region[0] < MIN_SIZE or region[3] - region[1] < MIN_SIZE:
            return
        if self.on_confirm is not None:
            self.on_confirm(region)

    def _cancel(self) -> None:
        if self.on_cancel is not None:
            self.on_cancel()

    # ------------------------------------------------------------ internals
    def _redraw(self, *_args: Any) -> None:
        self._background.pos = self.pos
        self._background.size = self.size
        region = self.region()
        if region[2] > region[0] and region[3] > region[1]:
            scale_x = self.picture.width / (self._picture_size[0] or 1)
            scale_y = self.picture.height / (self._picture_size[1] or 1)
            offset_x = self.picture.center_x - self.picture.width / 2
            offset_y = self.picture.center_y - self.picture.height / 2
            self._border.rectangle = (
                offset_x + region[0] / (scale_x or 1),
                offset_y + region[1] / (scale_y or 1),
                (region[2] - region[0]) / (scale_x or 1),
                (region[3] - region[1]) / (scale_y or 1),
            )
        else:
            self._border.rectangle = (0, 0, 0, 0)


class LensResult(FloatLayout):
    """The popup with what was read - the answer of the board."""

    #: Called when the teacher closes the popup.
    on_close: Callable[[], None] | None = None
    #: Called when the teacher wants the whole thing in the app.
    on_open: Callable[[str], None] | None = None

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("size_hint", (1, 1))
        super().__init__(**kwargs)
        self.reading = ""
        self._build()

    # ------------------------------------------------------------------ ui
    def _build(self) -> None:
        with self.canvas.before:
            Color(0, 0, 0, 0.72)
            self._background = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._redraw, size=self._redraw)

        card = BoxLayout(
            orientation="vertical",
            size_hint=(0.82, 0.78),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            padding=dp(theme.PANEL_PADDING_DP),
            spacing=dp(theme.GAP_DP),
        )

        self.reading_label = _label("", 26, theme.TEXT)
        self.reading_label.height = dp(44)
        card.add_widget(self.reading_label)

        self.answer_label = _label("", 20, theme.ACCENT)
        self.answer_label.height = dp(38)
        card.add_widget(self.answer_label)

        self.plot = KivyImage(
            size_hint_y=None,
            height=dp(220),
            allow_stretch=True,
            keep_ratio=True,
        )
        card.add_widget(self.plot)

        self.steps = _label("", 15, theme.TEXT_MUTED)
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.steps)
        card.add_widget(scroll)

        self.note = _label("", 13, theme.TEXT_MUTED)
        self.note.height = dp(24)
        card.add_widget(self.note)

        actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        open_button = _button("Open in the app", theme.SURFACE_ALT)
        open_button.bind(on_release=lambda _b: self._open())
        close = _button("Close", theme.PRIMARY)
        close.bind(on_release=lambda _b: self._close())
        actions.add_widget(open_button)
        actions.add_widget(close)
        card.add_widget(actions)

        self.add_widget(card)

    # ----------------------------------------------------------------- api
    def show(
        self,
        reading: str,
        answer: str = "",
        steps: list[dict[str, Any]] | None = None,
        plot: str = "",
        note: str = "",
    ) -> None:
        """Fill the popup with the result of the reading."""
        self.reading = reading or ""
        self.reading_label.text = self.reading
        self.answer_label.text = answer or ""
        self.plot.source = plot or ""
        self.plot.opacity = 1 if plot else 0
        self.steps.text = _steps_text(steps)
        self.note.text = note or ""

    def _open(self) -> None:
        if self.on_open is not None:
            self.on_open(self.reading)

    def _close(self) -> None:
        if self.on_close is not None:
            self.on_close()

    def _redraw(self, *_args: Any) -> None:
        self._background.pos = self.pos
        self._background.size = self.size


def _steps_text(steps: list[dict[str, Any]] | None) -> str:
    """The steps of the solution as text."""
    if not steps:
        return ""
    lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        text = step.get("text") or step.get("explanation") or step.get("latex") or ""
        if not text:
            continue
        lines.append(f"{index}. {text}")
    return "\n".join(lines)


__all__ = ["MIN_SIZE", "LensOverlay", "LensResult"]
