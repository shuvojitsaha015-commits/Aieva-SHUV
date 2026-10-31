"""The visual building blocks of the screens: the cards and the panels.

The widgets draw their own rounded surfaces, so the application needs no
image assets and stays sharp on every screen resolution - from a phone to a
4K interactive board.
"""

from __future__ import annotations

from typing import Any

from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

from aieva.ui import theme

#: The font of the glyphs - it is shipped with Kivy.
GLYPH_FONT = "fonts/DejaVuSans.ttf"


class Surface:
    """A rounded rectangle drawn on a widget.

    The border is a second, slightly larger rectangle behind the surface -
    the border of a rounded rectangle cannot be drawn with ``Line``, so this
    is the way to get a clean one pixel edge.
    """

    def __init__(
        self,
        widget: Any,
        bg_color: tuple[float, float, float, float],
        border_color: tuple[float, float, float, float] | None = None,
        radius: float | None = None,
    ) -> None:
        self.widget = widget
        self.corner = dp(radius if radius is not None else theme.RADIUS_DP)
        self.border_color = border_color
        self._rectangles: list[RoundedRectangle] = []
        with widget.canvas.before:
            if border_color is not None:
                Color(rgba=border_color)
                self._rectangles.append(RoundedRectangle(radius=[self.corner]))
            self.background = Color(rgba=bg_color)
            self._rectangles.append(RoundedRectangle(radius=[self.corner]))
        self.sync()

    def sync(self) -> None:
        """Keep the surface on the bounds of the widget."""
        width = dp(1.2) if self.border_color is not None else 0.0
        for index, rectangle in enumerate(self._rectangles):
            offset = width if index == 0 else 0.0
            rectangle.pos = (self.widget.x - offset, self.widget.y - offset)
            rectangle.size = (self.widget.width + 2 * offset, self.widget.height + 2 * offset)


class Panel(BoxLayout):
    """A rounded surface that groups a part of a screen."""

    def __init__(
        self,
        bg_color: tuple[float, float, float, float] | None = None,
        border_color: tuple[float, float, float, float] | None = None,
        radius: float | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(theme.PANEL_PADDING_DP))
        kwargs.setdefault("spacing", dp(theme.GAP_DP))
        super().__init__(**kwargs)
        self.surface = Surface(
            self,
            bg_color or theme.CARD,
            theme.BORDER if border_color is None else border_color,
            radius,
        )
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_args: Any) -> None:
        self.surface.sync()


class CardButton(Button):
    """A tile with a glyph, a title and a one line description.

    It is a real :class:`~kivy.uix.button.Button`, so the behaviour of a
    button (the focus, the keyboard, the touch) is the normal one - only the
    look is different.
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        glyph: str = "",
        accent: tuple[float, float, float, float] | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(theme.CARD_HEIGHT_DP))
        kwargs.setdefault("font_size", theme.sp_size(17))
        kwargs.setdefault("color", theme.TEXT)
        super().__init__(**kwargs)
        self.text = ""
        self.glyph = glyph
        self.card_title = title
        self.card_subtitle = subtitle
        self.accent = accent or theme.PRIMARY
        self._base_color = theme.CARD
        self.surface = Surface(self, self._base_color, theme.BORDER)
        self.bind(pos=self._sync, size=self._sync)
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        column = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(14), dp(18), dp(14)],
            spacing=dp(2),
        )

        self.glyph_label = Label(
            text=self.glyph,
            size_hint_y=None,
            height=dp(28),
            font_size=theme.sp_size(20),
            # Roboto has no symbols like the pencil or the gear - DejaVu does
            font_name=GLYPH_FONT,
            color=self.accent,
            halign="left",
            valign="middle",
        )
        self.glyph_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        column.add_widget(self.glyph_label)

        self.title_label = Label(
            text=self.card_title,
            size_hint_y=None,
            height=dp(28),
            font_size=theme.sp_size(19),
            color=theme.TEXT,
            halign="left",
            valign="middle",
        )
        self.title_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        column.add_widget(self.title_label)

        self.subtitle_label = Label(
            text=self.card_subtitle,
            size_hint_y=None,
            height=dp(34),
            font_size=theme.sp_size(13),
            color=theme.TEXT_MUTED,
            halign="left",
            valign="top",
        )
        self.subtitle_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        column.add_widget(self.subtitle_label)

        self.add_widget(column)
        self._column = column

    def _sync(self, *_args: Any) -> None:
        """Keep the surface and the content on the widget bounds."""
        self.surface.sync()
        # a button is not a layout, so the column is placed by hand
        self._column.pos = self.pos
        self._column.size = self.size

    # ------------------------------------------------------------ feedback
    def on_mouse_enter(self, *_args: Any) -> None:
        self._set_state(hovered=True)

    def on_mouse_leave(self, *_args: Any) -> None:
        self._set_state(hovered=False, pressed=False)

    def on_press(self) -> None:
        self._set_state(pressed=True)

    def on_release(self) -> None:
        self._set_state(pressed=False)

    def _set_state(self, hovered: bool = False, pressed: bool = False) -> None:
        """Lighten the card a little while the pointer is on it."""
        if pressed:
            color = theme.SURFACE_ALT
        elif hovered:
            color = (
                min(self._base_color[0] + 0.03, 1.0),
                min(self._base_color[1] + 0.03, 1.0),
                min(self._base_color[2] + 0.04, 1.0),
                1.0,
            )
        else:
            color = self._base_color
        self.surface.background.rgba = color


class Chip(Button):
    """A small rounded label that behaves like a button (the subject picker)."""

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("size_hint_x", None)
        kwargs.setdefault("height", dp(44))
        kwargs.setdefault("font_size", theme.sp_size(15))
        kwargs.setdefault("color", theme.TEXT_MUTED)
        super().__init__(text=text, **kwargs)
        self.width = dp(34) + dp(9) * len(text)
        self.surface = Surface(self, theme.SURFACE_ALT, theme.BORDER, radius=22)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_args: Any) -> None:
        self.surface.sync()

    def set_active(self, active: bool) -> None:
        """Show whether this chip is the selected one."""
        self.surface.background.rgba = theme.PRIMARY if active else theme.SURFACE_ALT
        self.color = theme.TEXT if active else theme.TEXT_MUTED


__all__ = ["GLYPH_FONT", "CardButton", "Chip", "Panel", "Surface"]
