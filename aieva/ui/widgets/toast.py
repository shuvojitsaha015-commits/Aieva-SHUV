"""A small toast notification (Kivy 2.x has no built in ``kivy.uix.toast``)."""

from __future__ import annotations

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from aieva.ui import theme


class Toast(BoxLayout):
    """A message that appears at the bottom of the window for a few seconds."""

    def __init__(self, text: str, duration: float = 3.0, **kwargs) -> None:
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("height", dp(56))
        kwargs.setdefault("padding", [dp(16), dp(8)])
        super().__init__(**kwargs)
        self.duration = duration
        label = Label(
            text=text,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
            halign="left",
            valign="middle",
        )
        label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        self.add_widget(label)
        self._label = label

    def show(self) -> None:
        """Attach the toast to the window and schedule its removal."""
        if self.parent is None:
            Window.add_widget(self)
        Clock.schedule_once(lambda _dt: self.dismiss(), self.duration)

    def dismiss(self) -> None:
        """Remove the toast from the window."""
        if self.parent is not None:
            self.parent.remove_widget(self)


def show_toast(message: str, duration: float = 3.0) -> None:
    """Show a short message at the bottom of the window (never raises)."""
    try:
        Toast(text=message, duration=duration).show()
    except Exception as exc:  # noqa: BLE001 - a toast must never break the app
        print(f"[aieva] {message} ({exc})")


__all__ = ["Toast", "show_toast"]
