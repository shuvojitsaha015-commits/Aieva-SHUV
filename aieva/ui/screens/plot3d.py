"""The 3D / 2D plot screen (feature 1.d).

The screen routes the input automatically: two free variables with a ``z`` go
to a 3D surface, everything else stays in 2D.
"""

from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner

from aieva.config import get_settings
from aieva.core.errors import AievaError
from aieva.core.user_settings import plot_quality
from aieva.plugins.math import plot3d
from aieva.ui import theme
from aieva.ui.widgets.controls import labelled_input, slider_row
from aieva.ui.widgets.header import ScreenHeader
from aieva.ui.widgets.plot3d_view import Plot3DView
from aieva.ui.widgets.toast import show_toast
from aieva.ui.workers import run_in_background


class Plot3DScreen(Screen):
    """Input, options and the rotatable 3D view."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = "plot3d"
        self.session: plot3d.Plot3DSession | None = None
        self._build()

    # ------------------------------------------------------------------ ui
    def _build(self) -> None:
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )
        root.add_widget(ScreenHeader("3D plots", "A surface you can rotate and zoom with a finger"))

        input_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.INPUT_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.expression_input = labelled_input("z = x**2 + y**2", "z = x**2 + y**2")
        input_row.add_widget(self.expression_input)
        self.quality_spinner = Spinner(
            text=plot_quality(get_settings().quality),
            values=["low", "medium", "high"],
            size_hint_x=None,
            width=dp(170),
            height=dp(44),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
        )
        input_row.add_widget(self.quality_spinner)
        draw_button = Button(
            text="Draw",
            size_hint_x=None,
            width=dp(120),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        draw_button.bind(on_release=lambda _b: self.update_plot())
        input_row.add_widget(draw_button)
        root.add_widget(input_row)

        options = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.wireframe_check = CheckBox(size_hint_x=None, width=dp(40))
        options.add_widget(Label(text="wireframe", color=theme.TEXT, font_size=theme.sp_size(14)))
        options.add_widget(self.wireframe_check)
        self.contour_check = CheckBox(size_hint_x=None, width=dp(40))
        options.add_widget(Label(text="contour", color=theme.TEXT, font_size=theme.sp_size(14)))
        options.add_widget(self.contour_check)
        root.add_widget(options)

        self.slider_box = BoxLayout(
            orientation="vertical", size_hint_y=None, height=0, spacing=dp(4)
        )
        root.add_widget(self.slider_box)

        self.view = Plot3DView()
        root.add_widget(self.view)

        self.info_label = Label(
            text="",
            size_hint_y=None,
            height=dp(48),
            font_size=theme.sp_size(14),
            color=theme.TEXT_MUTED,
            halign="left",
            valign="middle",
        )
        self.info_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        root.add_widget(self.info_label)

        self.add_widget(root)

    # ----------------------------------------------------------------- api
    def update_plot(self) -> None:
        """Parse the input and (re)build the session."""
        text = self.expression_input.text.strip()
        if not text:
            show_toast("Type an expression, for example z = x**2 + y**2")
            return
        try:
            spec = plot3d.parse_plot_spec(text)
        except AievaError as exc:
            show_toast(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - SymPy can be creative
            show_toast(f"Could not read the expression: {exc}")
            return

        quality = self.quality_spinner.text
        wireframe = self.wireframe_check.active
        contour = self.contour_check.active

        def work() -> plot3d.Plot3DSession:
            return plot3d.Plot3DSession(
                spec, quality=quality, show_wireframe=wireframe, show_contour=contour
            )

        def on_done(session: plot3d.Plot3DSession) -> None:
            self.session = session
            self.view.set_session(session)
            self._build_sliders(session)
            self.info_label.text = (
                f"{spec.kind} ({spec.dimension}) - mesh {session.spec and ''}"
                f"render {session.last_render_ms:.0f} ms"
            )

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, AievaError):
                show_toast(str(exc))
            else:
                show_toast(f"Could not build the plot: {exc}")

        run_in_background(work, on_done, on_error, name="aieva-plot3d")

    def _build_sliders(self, session: plot3d.Plot3DSession) -> None:
        self.slider_box.clear_widgets()
        self.sliders: dict[str, Any] = {}
        for spec in session.parameters:
            row, slider, _label = slider_row(
                spec.name,
                spec.min,
                spec.max,
                spec.default,
                spec.step,
                on_change=self._on_parameter,
            )
            self.slider_box.add_widget(row)
            self.sliders[spec.name] = slider
        self.slider_box.height = dp(len(self.sliders) * theme.SLIDER_HEIGHT_DP)

    def _on_parameter(self, _value: float) -> None:
        """A slider moved - rebuild the figure in a worker thread."""
        if self.session is None:
            return
        values = {name: float(slider.value) for name, slider in self.sliders.items()}
        session = self.session

        def work() -> None:
            for name, value in values.items():
                session.set_param(name, value)

        def on_done(_result: None) -> None:
            if self.view.plot_canvas is not None:
                self.view.plot_canvas.figure = session.figure
                self.view.plot_canvas.apply_view()
            self.info_label.text = f"render {session.last_render_ms:.0f} ms"

        def on_error(exc: BaseException) -> None:
            show_toast(f"Could not update the plot: {exc}")

        run_in_background(work, on_done, on_error, name="aieva-plot3d-param")


__all__ = ["Plot3DScreen"]
