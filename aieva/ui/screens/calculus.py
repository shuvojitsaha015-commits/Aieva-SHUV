"""The calculus screen: integral, Riemann sums, tangent animation, area between.

The maths lives in :mod:`aieva.plugins.math.calculus`; this screen only builds
the controls and drives the animation with the Kivy clock.
"""

from __future__ import annotations

from typing import Any

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from aieva.core.errors import AievaError
from aieva.plugins.math import calculus
from aieva.ui import theme
from aieva.ui.widgets.header import ScreenHeader
from aieva.ui.widgets.plot_canvas import PlotCanvas
from aieva.ui.widgets.toast import show_toast
from aieva.ui.workers import run_in_background

#: The available calculus modes.
MODES: tuple[str, ...] = ("integral", "riemann", "tangent", "area_between", "shape_area")

#: Frame rate of the tangent animation.
ANIMATION_INTERVAL = 1.0 / 60.0


class CalculusScreen(Screen):
    """Controls and plot for the calculus visualisations."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = "calculus"
        self.mode = "integral"
        self.session: calculus.TangentSession | None = None
        self._animation_event = None
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )
        root.add_widget(ScreenHeader("Calculus", "Integrals, Riemann sums and the tangent line"))

        modes = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        for mode in MODES:
            button = Button(
                text=mode.replace("_", " ").title(),
                background_normal="",
                background_color=theme.SURFACE_ALT,
                color=theme.TEXT,
                font_size=theme.sp_size(15),
            )
            button.bind(on_release=lambda _b, name=mode: self.set_mode(name))
            modes.add_widget(button)
        root.add_widget(modes)

        self.controls = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(3 * theme.SLIDER_HEIGHT_DP),
            spacing=dp(4),
        )
        root.add_widget(self.controls)

        self.plot_area = BoxLayout(orientation="vertical")
        root.add_widget(self.plot_area)

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

        bottom = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.INPUT_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.function_input = TextInput(
            text="sin(x)",
            multiline=False,
            hint_text="f(x), e.g. sin(x)",
            font_size=theme.sp_size(17),
            background_color=theme.SURFACE,
            foreground_color=theme.TEXT,
            cursor_color=theme.PRIMARY,
            padding=[dp(12), dp(14)],
        )
        self.second_input = TextInput(
            text="x**2",
            multiline=False,
            hint_text="g(x) for 'area between'",
            font_size=theme.sp_size(17),
            background_color=theme.SURFACE,
            foreground_color=theme.TEXT,
            cursor_color=theme.PRIMARY,
            padding=[dp(12), dp(14)],
        )
        self.second_input.opacity = 0.0
        self.second_input.disabled = True
        draw_button = Button(
            text="Draw",
            size_hint_x=None,
            width=dp(120),
            background_normal="",
            background_color=theme.ACCENT,
            color=theme.TEXT,
            font_size=theme.sp_size(17),
        )
        draw_button.bind(on_release=lambda _b: self.update_plot())
        bottom.add_widget(self.function_input)
        bottom.add_widget(self.second_input)
        bottom.add_widget(draw_button)
        root.add_widget(bottom)

        self.add_widget(root)
        self._rebuild_controls()

    # -------------------------------------------------------------- controls
    def _rebuild_controls(self) -> None:
        self.controls.clear_widgets()
        self.sliders: dict[str, Any] = {}

        if self.mode in ("integral", "riemann", "area_between"):
            self._add_slider("a", "lower bound", -10.0, 10.0, 0.0)
            self._add_slider("b", "upper bound", -10.0, 10.0, 3.14159)
        if self.mode == "riemann":
            self._add_slider("n", "subintervals", 1.0, 200.0, 20.0)
            self.method_spinner = Spinner(
                text="midpoint",
                values=list(calculus.RIEMANN_METHODS),
                size_hint_x=None,
                width=dp(160),
                height=dp(44),
                background_normal="",
                background_color=theme.SURFACE_ALT,
                color=theme.TEXT,
            )
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(theme.SLIDER_HEIGHT_DP),
                spacing=dp(theme.GAP_DP),
            )
            label = Label(text="method", color=theme.TEXT, font_size=theme.sp_size(15))
            row.add_widget(label)
            row.add_widget(self.method_spinner)
            self.controls.add_widget(row)
        if self.mode == "tangent":
            self._add_slider("x0", "tangent point", -10.0, 10.0, 0.0)
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(theme.SLIDER_HEIGHT_DP),
                spacing=dp(theme.GAP_DP),
            )
            self.play_button = Button(
                text="Play",
                size_hint_x=None,
                width=dp(140),
                background_normal="",
                background_color=theme.PRIMARY,
                color=theme.TEXT,
                font_size=theme.sp_size(15),
            )
            self.play_button.bind(on_release=lambda _b: self.toggle_animation())
            row.add_widget(self.play_button)
            self.controls.add_widget(row)
        if self.mode == "shape_area":
            self._add_slider("scale", "units per pixel", 0.01, 5.0, 0.1)

    def _add_slider(
        self, name: str, label: str, minimum: float, maximum: float, default: float
    ) -> None:
        from kivy.uix.slider import Slider

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.SLIDER_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        caption = Label(
            text=label,
            size_hint_x=None,
            width=dp(150),
            color=theme.TEXT,
            font_size=theme.sp_size(15),
            halign="left",
            valign="middle",
        )
        caption.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        slider = Slider(
            min=minimum,
            max=maximum,
            value=default,
            step=0.01 if maximum - minimum < 100 else 1.0,
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
            if self.mode == "tangent" and name == "x0" and self.session is not None:
                self.session.set_x0(value)
                self._redraw()

        slider.bind(value=_changed)
        row.add_widget(caption)
        row.add_widget(slider)
        row.add_widget(value_label)
        self.controls.add_widget(row)
        self.sliders[name] = slider

    # ----------------------------------------------------------------- API
    def set_mode(self, mode: str) -> None:
        """Switch the calculus mode."""
        if mode not in MODES:
            return
        self.mode = mode
        self.stop_animation()
        self._rebuild_controls()
        needs_second = mode == "area_between"
        self.second_input.opacity = 1.0 if needs_second else 0.0
        self.second_input.disabled = not needs_second
        self.info_label.text = ""

    def slider_value(self, name: str, default: float = 0.0) -> float:
        slider = self.sliders.get(name)
        if slider is None:
            return default
        return float(slider.value)

    def update_plot(self) -> None:
        """(Re)compute the visualisation for the current mode."""
        function = self.function_input.text.strip()
        if not function:
            show_toast("Type a function first, e.g. sin(x)")
            return
        mode = self.mode
        a = self.slider_value("a", 0.0)
        b = self.slider_value("b", 3.14159)

        if mode == "area_between":
            second = self.second_input.text.strip()
            if not second:
                show_toast("Type the second function, e.g. x**2")
                return
            work = lambda: calculus.area_between(function, second, a, b)  # noqa: E731
        elif mode == "riemann":
            method = getattr(self, "method_spinner", None)
            method_name = method.text if method is not None else "midpoint"
            n = int(self.slider_value("n", 20.0))
            work = lambda: calculus.riemann_view(function, a, b, n, method_name)  # noqa: E731
        elif mode == "tangent":
            x0 = self.slider_value("x0", 0.0)
            work = lambda: calculus.tangent_view(function, x0)  # noqa: E731
        elif mode == "shape_area":
            show_toast("Draw a closed shape on the whiteboard, then press 'Shape area'.")
            return
        else:
            work = lambda: calculus.integral_view(function, a, b)  # noqa: E731

        def on_done(result: Any) -> None:
            self._show(result)

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, AievaError):
                show_toast(str(exc))
            else:
                show_toast(f"Could not build the plot: {exc}")

        run_in_background(work, on_done, on_error, name="aieva-calculus")

    def _show(self, result: Any) -> None:
        """Show a computed visualisation."""
        self.plot_area.clear_widgets()
        if result.figure is not None:
            self.plot_area.add_widget(PlotCanvas(result.figure))

        meta = result.meta or {}
        lines: list[str] = []
        if meta.get("kind") == "integral":
            lines.append(f"exact = {meta.get('exact')}   numeric = {meta.get('numeric'):.8g}")
        elif meta.get("kind") == "riemann":
            lines.append(
                f"sum = {meta.get('sum'):.8g}   exact = {meta.get('exact'):.8g}   "
                f"error = {meta.get('error'):.3g}"
            )
        elif meta.get("kind") == "area_between":
            lines.append(f"area = {meta.get('area'):.8g}")
        elif meta.get("kind") == "tangent":
            lines.append(f"f'(x) = {meta.get('derivative')}")
        for warning in meta.get("warnings", []) or []:
            lines.append(f"! {warning}")
        self.info_label.text = "\n".join(lines)

        if meta.get("kind") == "tangent":
            self.session = calculus.TangentSession(
                self.function_input.text.strip(), self.slider_value("x0", 0.0)
            )
            self._redraw()

    def _redraw(self) -> None:
        for child in self.plot_area.children:
            if hasattr(child, "draw_idle"):
                child.draw_idle()

    # ------------------------------------------------------------ animation
    def toggle_animation(self) -> None:
        """Start or stop the tangent animation."""
        if self._animation_event is None:
            self._animation_event = Clock.schedule_interval(self._animate, ANIMATION_INTERVAL)
            if hasattr(self, "play_button"):
                self.play_button.text = "Pause"
        else:
            self.stop_animation()

    def stop_animation(self) -> None:
        """Stop the tangent animation."""
        if self._animation_event is not None:
            self._animation_event.cancel()
            self._animation_event = None
        if hasattr(self, "play_button"):
            self.play_button.text = "Play"

    def _animate(self, dt: float) -> None:
        if self.session is None:
            self.stop_animation()
            return
        self.session.step(dt)
        self._redraw()

    def on_pre_leave(self, *_args: Any) -> None:
        self.stop_animation()


__all__ = ["ANIMATION_INTERVAL", "MODES", "CalculusScreen"]
