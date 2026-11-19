"""The popup that shows a Matplotlib figure together with the parameter sliders.

The modal is deliberately *not* a Matplotlib widget: the sliders are native Kivy
widgets so they react to touch exactly the way a teacher expects, and the
redraw is throttled to ~30 Hz so that dragging a slider stays smooth.
"""

from __future__ import annotations

from typing import Any

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.popup import Popup

from aieva.core.models import ParamSpec
from aieva.core.plotting import FigureOwner
from aieva.plugins.math.equations import PlotSession
from aieva.ui import theme
from aieva.ui.widgets.plot_canvas import PlotCanvas
from aieva.ui.widgets.slider_panel import SliderPanel

#: Maximum update frequency of the plot while a slider is moving.
UPDATE_INTERVAL = 1.0 / 30.0


class PlotModal(Popup):
    """A popup with the figure, the sliders and a few actions."""

    session: ObjectProperty = ObjectProperty(None, allownone=True)
    canvas_widget: ObjectProperty = ObjectProperty(None, allownone=True)
    slider_panel: ObjectProperty = ObjectProperty(None, allownone=True)

    def __init__(
        self,
        figure: Any = None,
        session: PlotSession | None = None,
        parameters: list[ParamSpec] | None = None,
        latex: str = "",
        title: str = "Plot",
        owner: FigureOwner | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("size_hint", (0.85, 0.85))
        kwargs.setdefault("auto_dismiss", False)
        super().__init__(title=title, **kwargs)

        self.session = session
        self.latex = latex
        self._pending: dict[str, float] = {}
        self._scheduled = False

        # The modal shows the figure - it does not own it. The owner
        # (whoever built the figure) gives the memory back; that way a
        # second plot on another screen is never touched.
        self.owner = owner
        self._figure = figure

        self.content = self._build_content(figure, parameters or [])
        self.bind(on_open=self._on_open)
        self.bind(on_dismiss=self._on_dismiss)

    # ------------------------------------------------------------------ api
    @property
    def figure(self) -> Any:
        """The figure that is shown in the modal."""
        return self._figure

    def dispose(self) -> None:
        """Give the memory of the shown figure back.

        Only the figure of **this** modal is released - a plot that is
        shown somewhere else keeps working. Calling it twice is safe.
        """
        canvas = self.canvas_widget
        if canvas is not None:
            canvas.set_figure(None)
        self.canvas_widget = None
        self._figure = None
        self.session = None
        if self.owner is not None:
            self.owner.release()

    # ------------------------------------------------------------------ UI
    def _build_content(self, figure: Any, parameters: list[ParamSpec]) -> BoxLayout:
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )

        if figure is not None:
            self.canvas_widget = PlotCanvas(figure)
            self.canvas_widget.size_hint_y = 0.78
            root.add_widget(self.canvas_widget)
        else:
            placeholder = Button(
                text="No figure available",
                size_hint_y=0.78,
                background_normal="",
                background_color=theme.SURFACE,
                color=theme.TEXT_MUTED,
            )
            root.add_widget(placeholder)

        self.slider_panel = SliderPanel(parameters)
        self.slider_panel.size_hint_y = 0.14
        self.slider_panel.on_change = self._on_parameter_changed
        root.add_widget(self.slider_panel)

        actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )

        reset_button = Button(
            text="Reset params",
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        reset_button.bind(on_release=self._on_reset)

        copy_button = Button(
            text="Copy equation (LaTeX)",
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        copy_button.bind(on_release=self._on_copy)

        close_button = Button(
            text="Close",
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        close_button.bind(on_release=lambda _b: self.dismiss())

        actions.add_widget(reset_button)
        actions.add_widget(copy_button)
        actions.add_widget(close_button)
        root.add_widget(actions)
        return root

    # -------------------------------------------------------------- closing
    def dismiss(self, *_args: Any, **kwargs: Any) -> None:
        """Close the popup and release the figure it shows."""
        super().dismiss(*_args, **kwargs)
        self.dispose()

    # -------------------------------------------------------------- actions
    def _on_open(self, *_args: Any) -> None:
        if self.session is not None and self.slider_panel is not None:
            for name, value in self.session.params.items():
                self.slider_panel.set_value(name, value)

    def _on_dismiss(self, *_args: Any) -> None:
        """The popup is gone - the memory of the figure goes back."""
        self.dispose()

    def _on_parameter_changed(self, name: str, value: float) -> None:
        """Queue a parameter update and refresh at most 30 times per second."""
        if self.session is None:
            return
        self._pending[name] = value
        if self._scheduled:
            return
        self._scheduled = True
        Clock.schedule_once(self._apply_pending, UPDATE_INTERVAL)

    def _apply_pending(self, *_args: Any) -> None:
        self._scheduled = False
        if not self._pending or self.session is None:
            return
        pending, self._pending = self._pending, {}
        self.session.set_params(pending)
        self._redraw()

    def _redraw(self) -> None:
        if self.canvas_widget is not None:
            self.canvas_widget.draw_idle()

    def _on_reset(self, *_args: Any) -> None:
        if self.session is None:
            return
        self.session.reset_params()
        if self.slider_panel is not None:
            for name, value in self.session.params.items():
                self.slider_panel.set_value(name, value)
        self._redraw()

    def _on_copy(self, *_args: Any) -> None:
        if not self.latex:
            return
        try:
            Clipboard.copy(self.latex)
        except Exception:  # noqa: BLE001 - the clipboard is optional
            pass


__all__ = ["UPDATE_INTERVAL", "PlotModal"]
