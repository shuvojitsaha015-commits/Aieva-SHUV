"""Reusable Kivy controls (sliders, matrix entry grids, labelled inputs).

They are shared by the calculus and the linear algebra screens so that every
screen has the same look, the same touch sizes and the same behaviour.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput

from aieva.ui import theme


def slider_row(
    label: str,
    minimum: float,
    maximum: float,
    default: float,
    step: float | None = None,
    on_change: Callable[[float], None] | None = None,
    width: int = 150,
) -> tuple[BoxLayout, Slider, Label]:
    """A labelled slider row. Returns ``(row, slider, value_label)``."""
    row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(theme.SLIDER_HEIGHT_DP),
        spacing=dp(theme.GAP_DP),
    )
    caption = Label(
        text=label,
        size_hint_x=None,
        width=dp(width),
        color=theme.TEXT,
        font_size=theme.sp_size(15),
        halign="left",
        valign="middle",
    )
    caption.bind(size=lambda w, _v: setattr(w, "text_size", w.size))

    if step is None:
        step = 0.01 if (maximum - minimum) < 100 else 1.0
    slider = Slider(
        min=minimum,
        max=maximum,
        value=default,
        step=step,
        cursor_size=(dp(28), dp(28)),
    )
    value_label = Label(
        text=f"{default:g}",
        size_hint_x=None,
        width=dp(80),
        color=theme.TEXT_MUTED,
        font_size=theme.sp_size(14),
        halign="right",
        valign="middle",
    )
    value_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))

    def _changed(_widget: Any, value: float) -> None:
        value_label.text = f"{value:g}"
        if on_change is not None:
            on_change(float(value))

    slider.bind(value=_changed)
    row.add_widget(caption)
    row.add_widget(slider)
    row.add_widget(value_label)
    return row, slider, value_label


def matrix_grid(
    size: int = 2,
    values: list[list[float]] | None = None,
    cell_width: int = 90,
) -> tuple[GridLayout, list[list[TextInput]]]:
    """A grid of text inputs for entering a matrix. Returns ``(grid, cells)``."""
    grid = GridLayout(
        cols=size, spacing=dp(theme.GAP_DP), size_hint_y=None, height=dp(theme.INPUT_HEIGHT_DP)
    )
    cells: list[list[TextInput]] = []
    for row_index in range(size):
        row_cells: list[TextInput] = []
        for column_index in range(size):
            default = "0"
            if values is not None:
                default = f"{values[row_index][column_index]:g}"
            cell = TextInput(
                text=default,
                multiline=False,
                size_hint_x=None,
                width=dp(cell_width),
                height=dp(theme.INPUT_HEIGHT_DP),
                font_size=theme.sp_size(17),
                background_color=theme.SURFACE,
                foreground_color=theme.TEXT,
                cursor_color=theme.PRIMARY,
                padding=[dp(8), dp(14)],
            )
            row_cells.append(cell)
            grid.add_widget(cell)
        cells.append(row_cells)
    return grid, cells


def labelled_input(
    text: str = "",
    hint: str = "",
    width: int | None = None,
) -> TextInput:
    """A single line text input with the Aieva styling."""
    options: dict[str, Any] = {}
    if width:
        options["size_hint_x"] = None
        options["width"] = dp(width)
    return TextInput(
        text=text,
        multiline=False,
        hint_text=hint,
        **options,
        height=dp(theme.INPUT_HEIGHT_DP),
        font_size=theme.sp_size(17),
        background_color=theme.SURFACE,
        foreground_color=theme.TEXT,
        cursor_color=theme.PRIMARY,
        padding=[dp(12), dp(14)],
    )


def mode_button(text: str, color: tuple[float, float, float, float] | None = None) -> Button:
    """A mode / action button with the Aieva styling."""
    return Button(
        text=text,
        background_normal="",
        background_color=color or theme.SURFACE_ALT,
        color=theme.TEXT,
        font_size=theme.sp_size(15),
    )


__all__ = ["labelled_input", "matrix_grid", "mode_button", "slider_row"]
