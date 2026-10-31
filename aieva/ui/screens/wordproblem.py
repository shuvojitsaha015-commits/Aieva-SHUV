"""The word problem screen (Phase 9).

The flow is:

    text -> the LLM (through the server) makes a structured model ->
    the "here is how I understood it" card (the values can be corrected) ->
    the problem is solved with SymPy -> the steps, the picture and the sliders.

When the server is not reachable the screen falls back to the local model of
:func:`aieva.plugins.math.wordproblems.local_model`, so the application stays
usable on a board without an internet connection.

Nothing here blocks the UI thread: the server call and the symbolic work run
in worker threads.
"""

from __future__ import annotations

import logging
from typing import Any

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from aieva.core.errors import AievaError, CloudError
from aieva.plugins.math.wordproblems import (
    WordProblem,
    WordProblemSession,
    local_model,
)
from aieva.ui import theme
from aieva.ui.widgets.header import ScreenHeader
from aieva.ui.widgets.plot_canvas import PlotCanvas
from aieva.ui.widgets.slider_panel import SliderPanel
from aieva.ui.widgets.steps_panel import StepsPanel
from aieva.ui.widgets.toast import show_toast
from aieva.ui.workers import run_in_background

LOGGER = logging.getLogger(__name__)

#: Frames per second of the projectile animation.
ANIMATION_INTERVAL = 1.0 / 30.0

#: How long the screen waits for the server (seconds).
UI_TIMEOUT = 15.0

#: The examples that are offered when the screen opens.
EXAMPLES: tuple[str, ...] = (
    "A ball is thrown with 20 m/s at 45 degrees. How high does it fly and how far?",
    "A car drives at 15 m/s, a bus ahead of it drives at 10 m/s and is 200 m away. "
    "When does the car catch the bus?",
    "A farmer has 40 m of fence for a rectangular field against a wall. "
    "What is the largest area?",
    "A tank of 600 l receives 30 l/min and loses 20 l/min. How long until it is full?",
    "A rectangle is 5 m wide and 8 m long. What is its area and its perimeter?",
)


class WordProblemScreen(Screen):
    """Type a word problem, check the model, solve it and watch the picture."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = "wordproblem"
        self.problem: WordProblem | None = None
        self.session: WordProblemSession | None = None
        self._value_inputs: dict[str, TextInput] = {}
        self._animation_event: Any = None
        self._animation_index = 0
        self._animation_points: dict[str, Any] | None = None
        self._marker: Any = None
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )
        root.add_widget(
            ScreenHeader("Word problem", "Analyse it, confirm it and watch the picture")
        )

        # --- the text and the analyse button -----------------------------
        input_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.INPUT_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.problem_input = TextInput(
            text=EXAMPLES[0],
            multiline=False,
            hint_text="a word problem, e.g. 'a ball is thrown with 20 m/s at 45 degrees'",
            font_size=theme.sp_size(16),
            background_color=theme.SURFACE,
            foreground_color=theme.TEXT,
            cursor_color=theme.PRIMARY,
            padding=[dp(12), dp(14)],
        )
        input_row.add_widget(self.problem_input)

        analyse_button = Button(
            text="Analyse",
            size_hint_x=None,
            width=dp(150),
            background_normal="",
            background_color=theme.ACCENT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        analyse_button.bind(on_release=lambda _b: self.analyse())
        input_row.add_widget(analyse_button)
        root.add_widget(input_row)

        examples_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        for index, example in enumerate(EXAMPLES[:3]):
            button = Button(
                text=f"example {index + 1}",
                background_normal="",
                background_color=theme.SURFACE_ALT,
                color=theme.TEXT_MUTED,
                font_size=theme.sp_size(13),
            )
            button.bind(on_release=lambda _b, text=example: self._use_example(text))
            examples_row.add_widget(button)
        self.status_label = Label(
            text="",
            color=theme.TEXT_MUTED,
            font_size=theme.sp_size(13),
            halign="left",
            valign="middle",
        )
        self.status_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        examples_row.add_widget(self.status_label)
        root.add_widget(examples_row)

        # --- the confirmation card and the result ------------------------
        middle = BoxLayout(orientation="horizontal", spacing=dp(theme.GAP_DP))

        card_box = BoxLayout(orientation="vertical", size_hint_x=0.46, spacing=dp(theme.GAP_DP))
        self.card_title = Label(
            text="How I understood the problem",
            size_hint_y=None,
            height=dp(30),
            font_size=theme.sp_size(16),
            color=theme.PRIMARY,
            halign="left",
            valign="middle",
            bold=True,
        )
        self.card_title.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        card_box.add_widget(self.card_title)

        self.card = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.card.bind(minimum_height=self.card.setter("height"))
        card_scroll = ScrollView(do_scroll_x=False, bar_width=dp(8))
        card_scroll.add_widget(self.card)
        card_box.add_widget(card_scroll)

        self.confirm_button = Button(
            text="Confirm and solve",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        self.confirm_button.bind(on_release=lambda _b: self.solve())
        self.confirm_button.disabled = True
        card_box.add_widget(self.confirm_button)
        middle.add_widget(card_box)

        result_box = BoxLayout(orientation="vertical", spacing=dp(theme.GAP_DP))
        self.answer_label = Label(
            text="",
            size_hint_y=None,
            height=dp(40),
            font_size=theme.sp_size(17),
            color=theme.ACCENT,
            halign="left",
            valign="middle",
            bold=True,
        )
        self.answer_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        result_box.add_widget(self.answer_label)

        self.steps_panel = StepsPanel()
        result_box.add_widget(self.steps_panel)
        middle.add_widget(result_box)
        root.add_widget(middle)

        # --- the picture, the sliders and the actions --------------------
        bottom = BoxLayout(orientation="vertical", spacing=dp(theme.GAP_DP))
        self.plot_area = BoxLayout(orientation="vertical", size_hint_y=0.7)
        bottom.add_widget(self.plot_area)

        self.slider_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(2 * theme.SLIDER_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.slider_panel = SliderPanel([])
        self.slider_panel.on_change = self._on_parameter_changed
        self.slider_box.add_widget(self.slider_panel)
        bottom.add_widget(self.slider_box)

        actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.play_button = Button(
            text="Animate",
            size_hint_x=None,
            width=dp(150),
            background_normal="",
            background_color=theme.WARNING,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        self.play_button.bind(on_release=lambda _b: self.toggle_animation())
        self.play_button.disabled = True
        actions.add_widget(self.play_button)

        reset_button = Button(
            text="Reset values",
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        reset_button.bind(on_release=lambda _b: self.reset_values())
        actions.add_widget(reset_button)

        home_button = Button(
            text="Home",
            size_hint_x=None,
            width=dp(140),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        home_button.bind(on_release=lambda _b: self._go_home())
        actions.add_widget(home_button)
        bottom.add_widget(actions)
        root.add_widget(bottom)

        self.add_widget(root)
        self._show_card(None)

    # ---------------------------------------------------------------- the flow
    def _use_example(self, text: str) -> None:
        self.problem_input.text = text
        self.analyse()

    def analyse(self) -> None:
        """Ask the server for the structured model of the problem."""
        text = self.problem_input.text.strip()
        if not text:
            show_toast("Type a word problem first")
            return
        self.status_label.text = "Reading the problem..."
        self.confirm_button.disabled = True

        def work() -> WordProblem:
            from aieva.core.llm.client import AievaServerClient

            try:
                # the timeout of the UI is shorter than the one of the core:
                # a teacher should not wait a minute for a word problem
                payload = AievaServerClient(timeout=UI_TIMEOUT).word_problem(text)
            except CloudError as exc:
                LOGGER.info("The server is not reachable: %s", exc)
                return local_model(text)
            data = dict(payload)
            data.pop("note", None)
            data.pop("raw", None)
            data["source_text"] = text
            return WordProblem.from_dict(data)

        def on_done(problem: WordProblem) -> None:
            self.problem = problem
            self._show_card(problem)
            self.status_label.text = (
                "Check the values, then press 'Confirm and solve'."
                if problem.supported
                else "This problem type is not supported in v1."
            )
            self.confirm_button.disabled = not problem.supported

        def on_error(exc: BaseException) -> None:
            LOGGER.warning("The word problem could not be analysed: %s", exc)
            show_toast(f"Could not read the problem: {exc}")
            self.status_label.text = ""

        run_in_background(work, on_done, on_error, name="aieva-wordproblem")

    def solve(self) -> None:
        """Solve the (confirmed) model and draw it."""
        if self.problem is None:
            show_toast("Analyse a problem first")
            return
        problem = self.problem
        self._read_values(problem)
        self.status_label.text = "Solving..."

        def work() -> WordProblemSession:
            return WordProblemSession(problem)

        def on_done(session: WordProblemSession) -> None:
            self.session = session
            self.answer_label.text = session.solution.answer_text or "(no answer)"
            self.steps_panel.show_steps(list(session.solution.steps), title=problem.problem_type)
            self._show_figure(session)
            self._build_sliders(session)
            self.status_label.text = "Drag a slider to change the numbers."
            for warning in session.solution.warnings:
                show_toast(warning)

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, AievaError):
                show_toast(str(exc))
            else:
                show_toast(f"Could not solve the problem: {exc}")
            self.status_label.text = "Could not solve the problem."

        run_in_background(work, on_done, on_error, name="aieva-wordproblem-solve")

    # ------------------------------------------------------------- the card
    def _show_card(self, problem: WordProblem | None) -> None:
        """The "here is how I understood it" card."""
        self.card.clear_widgets()
        self._value_inputs.clear()
        if problem is None:
            self.card.add_widget(self._card_label("Nothing analysed yet.", theme.TEXT_MUTED))
            return

        self.card.add_widget(self._card_label(f"type: {problem.problem_type}", theme.ACCENT))
        if problem.variables:
            grid = GridLayout(cols=3, size_hint_y=None, spacing=dp(6), height=dp(40))
            grid.bind(minimum_height=grid.setter("height"))
            for variable in problem.variables:
                grid.add_widget(self._card_label(variable.name, theme.TEXT))
                entry = TextInput(
                    text="" if variable.value is None else f"{variable.value:g}",
                    multiline=False,
                    size_hint_y=None,
                    height=dp(44),
                    font_size=theme.sp_size(15),
                    background_color=theme.SURFACE,
                    foreground_color=theme.TEXT,
                    cursor_color=theme.PRIMARY,
                    padding=[dp(8), dp(10)],
                )
                grid.add_widget(entry)
                grid.add_widget(self._card_label(variable.unit or "-", theme.TEXT_MUTED))
                self._value_inputs[variable.name] = entry
            self.card.add_widget(grid)
        else:
            self.card.add_widget(self._card_label("No variables in the model.", theme.TEXT_MUTED))

        for equation in problem.equations:
            self.card.add_widget(self._card_label(f"equation: {equation}", theme.TEXT))
        if problem.unknowns:
            self.card.add_widget(
                self._card_label(f"unknowns: {', '.join(problem.unknowns)}", theme.TEXT_MUTED)
            )
        if problem.assumptions:
            self.card.add_widget(
                self._card_label(f"assumptions: {', '.join(problem.assumptions)}", theme.TEXT_MUTED)
            )
        if problem.visualization_hint:
            self.card.add_widget(
                self._card_label(f"picture: {problem.visualization_hint}", theme.TEXT_MUTED)
            )
        if not problem.supported:
            self.card.add_widget(
                self._card_label("This type is not supported in v1.", theme.WARNING)
            )

    def _card_label(self, text: str, color: tuple[float, float, float, float]) -> Label:
        label = Label(
            text=text,
            size_hint_y=None,
            height=dp(30),
            font_size=theme.sp_size(14),
            color=color,
            halign="left",
            valign="middle",
        )
        label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        return label

    def _read_values(self, problem: WordProblem) -> None:
        """Copy the edited values back into the model."""
        for variable in problem.variables:
            entry = self._value_inputs.get(variable.name)
            if entry is None:
                continue
            try:
                variable.value = float(entry.text.strip().replace(",", "."))
            except ValueError:
                show_toast(f"{variable.name} is not a number - the old value is kept")

    # ------------------------------------------------------------ the result
    def _show_figure(self, session: WordProblemSession) -> None:
        self.plot_area.clear_widgets()
        self._marker = None
        if session.figure is not None:
            self.plot_area.add_widget(PlotCanvas(session.figure))

    def _build_sliders(self, session: WordProblemSession) -> None:
        """Replace the sliders with the ones of the solved problem."""
        self.slider_box.clear_widgets()
        self.slider_panel = SliderPanel(session.parameters)
        self.slider_panel.on_change = self._on_parameter_changed
        self.slider_box.add_widget(self.slider_panel)
        self.slider_box.height = dp(max(len(session.parameters), 1) * theme.SLIDER_HEIGHT_DP)
        self._animation_points = session.animation_points()
        self.play_button.disabled = self._animation_points is None
        self.stop_animation()

    def _on_parameter_changed(self, name: str, value: float) -> None:
        """A slider moved - solve and draw again (in a worker thread)."""
        if self.session is None:
            return

        def work() -> float:
            return self.session.set_param(name, value)

        def on_done(_elapsed: float) -> None:
            if self.session is None:
                return
            self.answer_label.text = self.session.solution.answer_text or "(no answer)"
            self.steps_panel.show_steps(
                list(self.session.solution.steps), title=self.session.problem.problem_type
            )
            # the template draws a new figure - the canvas has to follow
            self._show_figure(self.session)
            self._redraw()
            self._animation_points = self.session.animation_points()
            self.play_button.disabled = self._animation_points is None

        def on_error(exc: BaseException) -> None:
            LOGGER.info("The parameter could not be changed: %s", exc)

        run_in_background(work, on_done, on_error, name="aieva-wordproblem-param")

    def _redraw(self) -> None:
        for child in self.plot_area.children:
            if hasattr(child, "draw_idle"):
                child.draw_idle()

    def reset_values(self) -> None:
        """Put the values of the model back."""
        if self.problem is None:
            return
        for variable in self.problem.variables:
            entry = self._value_inputs.get(variable.name)
            if entry is not None and variable.value is not None:
                entry.text = f"{variable.value:g}"
        self.solve()

    # ----------------------------------------------------------- animation
    def toggle_animation(self) -> None:
        """Start or stop the flight of the ball."""
        if self._animation_event is None:
            if self._animation_points is None:
                show_toast("Only the projectile can be animated")
                return
            self._animation_index = 0
            self._animation_event = Clock.schedule_interval(self._animate, ANIMATION_INTERVAL)
            self.play_button.text = "Stop"
        else:
            self.stop_animation()

    def stop_animation(self) -> None:
        if self._animation_event is not None:
            self._animation_event.cancel()
            self._animation_event = None
        if hasattr(self, "play_button"):
            self.play_button.text = "Animate"

    def _animate(self, _dt: float) -> None:
        """Move the marker along the trajectory."""
        points = self._animation_points
        if points is None or self.session is None:
            self.stop_animation()
            return
        times = points["times"]
        index = self._animation_index
        if index >= len(times):
            self.stop_animation()
            return
        self._animation_index = index + 1
        if self._marker is None:
            axes = self.session.figure.get_axes()
            if not axes:
                self.stop_animation()
                return
            (self._marker,) = axes[0].plot([], [], "o", color="#d62728", markersize=8, zorder=6)
        self._marker.set_data([points["x"][index]], [points["y"][index]])
        self._redraw()

    # ------------------------------------------------------------ internals
    def _go_home(self) -> None:
        self.stop_animation()
        if self.manager is not None:
            self.manager.current = "home"

    def on_pre_leave(self, *_args: Any) -> None:
        self.stop_animation()


__all__ = ["ANIMATION_INTERVAL", "EXAMPLES", "WordProblemScreen"]
