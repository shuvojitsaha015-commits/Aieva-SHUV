"""One labelled Kivy slider per parameter.

Every row shows the parameter name, its live value and two fine tuning buttons
(``-`` / ``+``) that move the parameter by one step. The panel emits
:attr:`SliderPanel.changed` with ``(name, value)`` whenever something moves.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider

from aieva.core.models import ParamSpec
from aieva.ui import theme


class SliderRow(BoxLayout):
    """A single parameter row."""

    #: Called with ``(name, value)`` whenever the value changes.
    on_change: Callable[[str, float], None] | None = None

    name: str = ""
    spec: ObjectProperty = ObjectProperty(None, allownone=True)

    def __init__(self, spec: ParamSpec, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.spec = spec
        self.name = spec.name
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(theme.SLIDER_HEIGHT_DP)
        self.spacing = dp(theme.GAP_DP)

        self.name_label = Label(
            text=spec.name,
            size_hint_x=None,
            width=dp(70),
            font_size=theme.sp_size(16),
            color=theme.TEXT,
            halign="left",
            valign="middle",
        )
        self.name_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))

        self.minus_button = Button(
            text="-",
            size_hint_x=None,
            width=dp(48),
            height=dp(44),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            font_size=theme.sp_size(18),
        )
        self.minus_button.bind(on_release=lambda _b: self.nudge(-1))

        self.slider = Slider(
            min=spec.min,
            max=spec.max,
            step=spec.step,
            value=spec.default,
            size_hint_x=1,
            cursor_size=(dp(28), dp(28)),
        )
        self.slider.bind(value=self._on_slider)

        self.plus_button = Button(
            text="+",
            size_hint_x=None,
            width=dp(48),
            height=dp(44),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            font_size=theme.sp_size(18),
        )
        self.plus_button.bind(on_release=lambda _b: self.nudge(1))

        self.value_label = Label(
            text=f"{spec.default:g}",
            size_hint_x=None,
            width=dp(70),
            font_size=theme.sp_size(15),
            color=theme.TEXT_MUTED,
            halign="right",
            valign="middle",
        )
        self.value_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))

        self.add_widget(self.name_label)
        self.add_widget(self.minus_button)
        self.add_widget(self.slider)
        self.add_widget(self.plus_button)
        self.add_widget(self.value_label)

    # ----------------------------------------------------------------- API
    def nudge(self, direction: int) -> None:
        """Move the parameter by one step in ``direction``."""
        spec = self.spec
        if spec is None:
            return
        step = spec.step or 0.1
        value = self.slider.value + direction * step
        value = max(spec.min, min(spec.max, value))
        self.slider.value = value
        self._emit()

    def set_value(self, value: float, emit: bool = True) -> None:
        """Move the slider to ``value``."""
        spec = self.spec
        if spec is not None:
            value = max(spec.min, min(spec.max, float(value)))
        if abs(self.slider.value - value) < 1e-12:
            self._update_label()
            return
        self.slider.value = value
        self._update_label()
        if emit:
            self._emit()

    @property
    def value(self) -> float:
        return float(self.slider.value)

    # ------------------------------------------------------------ internals
    def _on_slider(self, _widget: Any, value: float) -> None:
        self._update_label()
        self._emit()

    def _update_label(self) -> None:
        self.value_label.text = f"{self.slider.value:g}"

    def _emit(self) -> None:
        if self.on_change is not None:
            self.on_change(self.name, float(self.slider.value))


class SliderPanel(BoxLayout):
    """A vertical stack of :class:`SliderRow` widgets."""

    #: Called with ``(name, value)`` whenever one of the sliders moves.
    on_change: Callable[[str, float], None] | None = None

    def __init__(self, specs: list[ParamSpec] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.spacing = dp(theme.GAP_DP)
        self.rows: dict[str, SliderRow] = {}
        for spec in specs or []:
            self.add_spec(spec)

    def add_spec(self, spec: ParamSpec) -> SliderRow:
        """Append a row for ``spec``."""
        row = SliderRow(spec)
        row.on_change = self._on_row_change
        self.rows[spec.name] = row
        self.add_widget(row)
        return row

    def set_value(self, name: str, value: float) -> None:
        """Move one slider without emitting a change event."""
        row = self.rows.get(name)
        if row is not None:
            row.set_value(value, emit=False)

    def values(self) -> dict[str, float]:
        """The current value of every slider."""
        return {name: row.value for name, row in self.rows.items()}

    # ------------------------------------------------------------ internals
    def _on_row_change(self, name: str, value: float) -> None:
        if self.on_change is not None:
            self.on_change(name, value)


__all__ = ["SliderPanel", "SliderRow"]
