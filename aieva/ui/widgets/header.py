"""The title bar of a screen: the name of the screen and a short line."""

from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from aieva.ui import theme


class ScreenHeader(BoxLayout):
    """The heading of a screen - the title and one line of context."""

    def __init__(self, title: str, subtitle: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(56))
        kwargs.setdefault("spacing", dp(0))
        super().__init__(**kwargs)

        self.title_label = Label(
            text=title,
            size_hint_y=None,
            height=dp(30),
            font_size=theme.sp_size(22),
            color=theme.TEXT,
            halign="left",
            valign="middle",
        )
        self.title_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        self.add_widget(self.title_label)

        self.subtitle_label = Label(
            text=subtitle,
            size_hint_y=None,
            height=dp(22),
            font_size=theme.sp_size(13),
            color=theme.TEXT_MUTED,
            halign="left",
            valign="middle",
        )
        self.subtitle_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        self.add_widget(self.subtitle_label)


__all__ = ["ScreenHeader"]
