"""The navigation bar of the application.

The bar is the same on every screen - it is the only way to reach the
*Settings*, so the teacher never has to hunt for it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

from aieva.ui import theme
from aieva.ui.widgets.card import GLYPH_FONT


class TabItem(Button):
    """One entry of the navigation bar."""

    def __init__(self, label: str, **kwargs: Any) -> None:
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", theme.TEXT_MUTED)
        kwargs.setdefault("font_size", theme.sp_size(16))
        kwargs.setdefault("size_hint_x", None)
        super().__init__(text=label, **kwargs)
        self.width = dp(26) + dp(9) * len(label)
        with self.canvas.before:
            self._indicator = Color(rgba=(0, 0, 0, 0))
            self._bar = RoundedRectangle(pos=self.pos, size=(dp(26), dp(3)), radius=[dp(2)])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_args: Any) -> None:
        self._bar.pos = (self.center_x - dp(13), self.y + dp(6))
        self._bar.size = (dp(26), dp(3))

    def set_active(self, active: bool) -> None:
        """Show whether this tab is the current one."""
        self.color = theme.TEXT if active else theme.TEXT_MUTED
        self._indicator.rgba = theme.PRIMARY if active else (0, 0, 0, 0)


class Brand(BoxLayout):
    """The name of the application at the left of the navigation bar."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_x", None)
        kwargs.setdefault("width", dp(150))
        kwargs.setdefault("spacing", dp(10))
        super().__init__(**kwargs)

        mark = Label(
            text="\u25a0",
            font_size=theme.sp_size(16),
            font_name=GLYPH_FONT,
            color=theme.PRIMARY,
            size_hint_x=None,
            width=dp(14),
        )
        self.add_widget(mark)

        label = Label(
            text="Aieva",
            font_size=theme.sp_size(21),
            color=theme.TEXT,
            halign="left",
            valign="middle",
            bold=True,
        )
        label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        self.add_widget(label)


class TabBar(BoxLayout):
    """The navigation bar: the destinations of the application.

    ``tabs`` is a list of ``(screen_name, label)`` pairs. The bar tells the
    application which screen was chosen with :attr:`on_select`.
    """

    #: Called with the name of the screen when a tab is pressed.
    on_select: Callable[[str], None] | None = None

    def __init__(self, tabs: list[tuple[str, str]], brand: bool = True, **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(theme.TITLE_BAR_DP))
        kwargs.setdefault("spacing", dp(4))
        kwargs.setdefault("padding", [dp(16), dp(6), dp(16), dp(6)])
        super().__init__(**kwargs)
        self.items: dict[str, TabItem] = {}
        if brand:
            self.add_widget(Brand())
        for screen_name, label in tabs:
            item = TabItem(label)
            item.bind(on_release=lambda _b, name=screen_name: self.select(name))
            self.items[screen_name] = item
            self.add_widget(item)
        self.current = ""

    def select(self, screen_name: str, notify: bool = True) -> None:
        """Highlight a tab (and tell the application about it)."""
        self.current = screen_name
        for name, item in self.items.items():
            item.set_active(name == screen_name)
        if notify and self.on_select is not None:
            self.on_select(screen_name)

    def highlight(self, screen_name: str) -> None:
        """Highlight a tab without changing the screen."""
        self.select(screen_name, notify=False)


__all__ = ["Brand", "TabBar", "TabItem"]
