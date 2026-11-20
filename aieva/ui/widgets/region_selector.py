"""The region selector: the user drags a rectangle over a capture.

It is a full screen overlay with a semi transparent background, a draggable
selection and a confirm / cancel pair of buttons. The result is a rectangle in
the pixel coordinates of the capture (top-down, matching desktop screen coordinates).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout

from aieva.ui import theme

#: The smallest selection the user may make (pixels).
MIN_SIZE = 24


class RegionSelector(FloatLayout):
    """Ask the user for a rectangle."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("size_hint", (1, 1))
        super().__init__(**kwargs)
        self.on_confirm: Callable[[tuple[int, int, int, int]], None] | None = None
        self.on_cancel: Callable[[], None] | None = None
        self.start: tuple[float, float] | None = None
        self.current: tuple[float, float] | None = None
        self._build()

    # ------------------------------------------------------------------ ui
    def _build(self) -> None:
        with self.canvas.before:
            Color(0, 0, 0, 0.40)
            self._background = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            Color(theme.ACCENT[0], theme.ACCENT[1], theme.ACCENT[2], 1)
            self._border = Line(rectangle=(0, 0, 0, 0), width=2.0)
        self.bind(pos=self._redraw, size=self._redraw)

        buttons = BoxLayout(
            orientation="horizontal",
            size_hint=(0.5, None),
            height=dp(48),
            pos_hint={"center_x": 0.5, "center_y": 0.08},
            spacing=dp(theme.GAP_DP),
        )
        cancel = Button(
            text="✕ Cancel",
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(15),
        )
        cancel.bind(on_release=lambda _b: self._cancel())

        confirm = Button(
            text="✓ Solve this area",
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(15),
            bold=True,
        )
        confirm.bind(on_release=lambda _b: self._confirm())

        buttons.add_widget(cancel)
        buttons.add_widget(confirm)
        self.add_widget(buttons)

    # --------------------------------------------------------------- touch
    def on_touch_down(self, touch: Any) -> bool:
        if not self.collide_point(*touch.pos):
            return False
        # If touched inside buttons, let buttons handle it
        for child in self.children:
            if child.collide_point(*touch.pos):
                return super().on_touch_down(touch)
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
            return super().on_touch_up(touch)
        self.current = touch.pos
        self._redraw()
        return True

    # ----------------------------------------------------------------- api
    def region(self) -> tuple[int, int, int, int]:
        """The selected rectangle (left, top, right, bottom)."""
        if self.start is None or self.current is None:
            return (0, 0, 0, 0)
        left = int(min(self.start[0], self.current[0]))
        right = int(max(self.start[0], self.current[0]))
        top = int(min(self.start[1], self.current[1]))
        bottom = int(max(self.start[1], self.current[1]))
        return (left, top, right, bottom)

    def reset(self) -> None:
        """Forget the current selection."""
        self.start = None
        self.current = None
        self._redraw()

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
        if self.start is not None and self.current is not None:
            x_min = min(self.start[0], self.current[0])
            x_max = max(self.start[0], self.current[0])
            y_min = min(self.start[1], self.current[1])
            y_max = max(self.start[1], self.current[1])
            self._border.rectangle = (
                x_min,
                y_min,
                x_max - x_min,
                y_max - y_min,
            )
        else:
            self._border.rectangle = (0, 0, 0, 0)


__all__ = ["MIN_SIZE", "RegionSelector"]
