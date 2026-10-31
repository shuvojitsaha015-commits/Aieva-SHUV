"""Manual text / LaTeX input with a "Plot" button."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kivy.metrics import dp
from kivy.properties import BooleanProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from aieva.ui import theme


class InputBar(BoxLayout):
    """A text field plus a mode switch and the *Plot* button.

    :attr:`on_submit` is called with ``(text, kind)`` where ``kind`` is
    ``"text"`` or ``"latex"``.
    """

    #: Called with ``(text, kind)`` when the user submits an equation.
    on_submit: Callable[[str, str], None] | None = None

    text: StringProperty = StringProperty("")
    kind: StringProperty = StringProperty("text")
    hint: StringProperty = StringProperty("")
    busy: BooleanProperty = BooleanProperty(False)

    text_input: ObjectProperty = ObjectProperty(None)
    latex_toggle: ObjectProperty = ObjectProperty(None)
    text_toggle: ObjectProperty = ObjectProperty(None)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        # the buttons are INPUT_HEIGHT_DP tall, the padding is around them
        self.height = dp(theme.INPUT_HEIGHT_DP + 2 * theme.PANEL_PADDING_DP)
        self.padding = dp(theme.PANEL_PADDING_DP)
        self.spacing = dp(theme.GAP_DP)
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        self.text_toggle = ToggleButton(
            text="Text",
            group="input-kind",
            state="down",
            size_hint_x=None,
            width=dp(90),
            height=dp(theme.BUTTON_HEIGHT_DP),
            background_normal="",
            background_color=theme.PRIMARY,
        )
        self.text_toggle.bind(on_press=lambda _b: self.set_kind("text"))

        self.latex_toggle = ToggleButton(
            text="LaTeX",
            group="input-kind",
            size_hint_x=None,
            width=dp(90),
            height=dp(theme.BUTTON_HEIGHT_DP),
            background_normal="",
            background_color=theme.SURFACE_ALT,
        )
        self.latex_toggle.bind(on_press=lambda _b: self.set_kind("latex"))

        self.text_input = TextInput(
            text=self.text,
            multiline=False,
            hint_text=self.hint or "Type an equation, e.g. y = m*x + c",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            font_size=theme.sp_size(18),
            background_color=theme.SURFACE,
            foreground_color=theme.TEXT,
            cursor_color=theme.PRIMARY,
            padding=[dp(12), dp(14)],
        )
        self.text_input.bind(text=lambda _w, value: setattr(self, "text", value))
        self.text_input.bind(on_text_validate=self._submit)

        plot_button = Button(
            text="Plot",
            size_hint_x=None,
            width=dp(120),
            height=dp(theme.BUTTON_HEIGHT_DP),
            background_normal="",
            background_color=theme.ACCENT,
            font_size=theme.sp_size(18),
        )
        plot_button.bind(on_release=self._submit)

        self.add_widget(self.text_toggle)
        self.add_widget(self.latex_toggle)
        self.add_widget(self.text_input)
        self.add_widget(plot_button)

    # ----------------------------------------------------------------- API
    def set_kind(self, kind: str) -> None:
        """Switch between the ``"text"`` and the ``"latex"`` mode."""
        self.kind = kind
        if kind == "latex":
            self.latex_toggle.state = "down"
            self.text_toggle.state = "normal"
            self.text_input.hint_text = "LaTeX, e.g. x^{2} + y^{2} = r^{2}"
        else:
            self.text_toggle.state = "down"
            self.latex_toggle.state = "normal"
            self.text_input.hint_text = "Type an equation, e.g. y = m*x + c"

    def set_text(self, value: str) -> None:
        """Replace the content of the input field."""
        self.text = value
        if self.text_input is not None:
            self.text_input.text = value

    def clear(self) -> None:
        """Empty the input field."""
        self.set_text("")

    # -------------------------------------------------------------- internal
    def _submit(self, *_args: Any) -> None:
        value = self.text.strip()
        if not value:
            return
        if self.on_submit is not None:
            self.on_submit(value, self.kind)


__all__ = ["InputBar"]
