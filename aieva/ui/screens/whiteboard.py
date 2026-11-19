"""The whiteboard screen: draw an equation, then plot it."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen

from aieva.ui import theme
from aieva.ui.widgets.header import ScreenHeader
from aieva.ui.widgets.input_bar import InputBar
from aieva.ui.widgets.whiteboard import Whiteboard


class WhiteboardScreen(Screen):
    """A drawing surface with pen tools and the manual input bar."""

    #: Called with ``(text, kind)`` when the user submits an equation.
    on_request_plot: Callable[[str, str], None] | None = None
    #: Called with the exported image when the user asks to solve the board.
    on_request_solve: Callable[[Any], None] | None = None
    #: Called with the exported image when the user asks to read the board.
    on_request_read: Callable[[Any], None] | None = None
    #: Called with the exported image every time the writing changes.
    on_canvas_changed: Callable[[Any], None] | None = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = "whiteboard"
        self._build()

    def apply_settings(self, settings: Any) -> None:
        """Take the pen and the palm rejection from the user settings."""
        whiteboard = getattr(self, "whiteboard", None)
        if whiteboard is None or settings is None:
            return
        whiteboard.pen_width = settings.pen_width
        whiteboard.palm_rejection = settings.palm_rejection
        whiteboard.palm_threshold = settings.palm_threshold

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )
        root.add_widget(
            ScreenHeader("Whiteboard", "Draw an equation with the finger, then plot it")
        )

        tools = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )

        self.pen_buttons: list[Button] = []
        for name in ("black", "red", "blue", "green", "yellow"):
            button = Button(
                text=name.capitalize(),
                size_hint_x=None,
                width=dp(96),
                background_normal="",
                background_color=theme.PEN_PALETTE.get(name),
                color=theme.TEXT,
                font_size=theme.sp_size(14),
            )
            button.bind(on_release=lambda _b, colour=name: self._set_pen(colour))
            self.pen_buttons.append(button)
            tools.add_widget(button)

        self.eraser_button = Button(
            text="Eraser",
            size_hint_x=None,
            width=dp(96),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(14),
        )
        self.eraser_button.bind(on_release=lambda _b: self._toggle_eraser())
        tools.add_widget(self.eraser_button)

        clear_button = Button(
            text="Clear",
            size_hint_x=None,
            width=dp(96),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(14),
        )
        clear_button.bind(on_release=lambda _b: self.whiteboard.clear())
        tools.add_widget(clear_button)

        undo_button = Button(
            text="Undo",
            size_hint_x=None,
            width=dp(96),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(14),
        )
        undo_button.bind(on_release=lambda _b: self.whiteboard.undo())
        tools.add_widget(undo_button)

        read_button = Button(
            text="Read the board",
            size_hint_x=None,
            width=dp(150),
            background_normal="",
            background_color=theme.ACCENT,
            color=theme.TEXT,
            font_size=theme.sp_size(14),
        )
        read_button.bind(on_release=lambda _b: self._request_read())
        tools.add_widget(read_button)

        solve_button = Button(
            text="Solve board",
            size_hint_x=None,
            width=dp(140),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(14),
        )
        solve_button.bind(on_release=lambda _b: self._request_solve())
        tools.add_widget(solve_button)

        root.add_widget(tools)

        self.whiteboard = Whiteboard()
        # Every change of the writing reaches the application - the
        # background service has to know that the board has something new.
        self.whiteboard.on_change = self._on_widget_changed
        root.add_widget(self.whiteboard)

        self.input_bar = InputBar()
        self.input_bar.on_submit = self._on_submitted
        root.add_widget(self.input_bar)

        self.add_widget(root)

    # ----------------------------------------------------------------- API
    def _set_pen(self, colour: str) -> None:
        self.whiteboard.set_eraser(False)
        self.whiteboard.set_pen_color(colour)

    def _toggle_eraser(self) -> None:
        self.whiteboard.set_eraser(not self.whiteboard.eraser)

    def _request_solve(self) -> None:
        if self.on_request_solve is not None:
            self.on_request_solve(self.whiteboard.export_to_image())

    def _request_read(self) -> None:
        """The teacher taps 'Read the board' - the writing is read now."""
        image = self.whiteboard.export_to_image()
        if self.on_request_read is not None:
            self.on_request_read(image)
        self._announce_change(image)

    def _announce_change(self, image: Any) -> None:
        """Tell the application that the board has changed."""
        if self.on_canvas_changed is not None:
            self.on_canvas_changed(image)

    def _on_widget_changed(self) -> None:
        """The writing on the canvas changed."""
        self._announce_change(self.whiteboard.export_to_image())

    def notify_change(self) -> None:
        """The writing changed - the background service has to know."""
        if self.on_canvas_changed is not None:
            self.on_canvas_changed(self.whiteboard.export_to_image())

    def _on_submitted(self, text: str, kind: str) -> None:
        if self.on_request_plot is not None:
            self.on_request_plot(text, kind)


__all__ = ["WhiteboardScreen"]
