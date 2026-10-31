"""The "Solve from Screen" screen (feature 1.e).

The flow is:

    capture -> region selection -> OCR (background) -> classify -> solve ->
    steps panel (+ a Visualise button when the problem can be plotted)

The OCR runs in the background worker, the symbolic work in a worker thread -
the UI thread is never blocked.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from aieva.core.errors import AievaError
from aieva.core.models import Step
from aieva.plugins.math.classify import classify
from aieva.plugins.math.solver import solve_expression
from aieva.ui import theme
from aieva.ui.widgets.controls import labelled_input
from aieva.ui.widgets.header import ScreenHeader
from aieva.ui.widgets.region_selector import RegionSelector
from aieva.ui.widgets.steps_panel import StepsPanel
from aieva.ui.widgets.toast import show_toast
from aieva.ui.workers import run_in_background

LOGGER = logging.getLogger(__name__)


class SolverScreen(Screen):
    """Solve a problem that was typed or read from the screen."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = "solver"
        self.ocr_worker: Any = None
        self.capture_provider: Callable[[], Any] | None = None
        self.on_visualize: Callable[[str, str], None] | None = None
        self.last_expression = ""
        self._selector: RegionSelector | None = None
        self._build()

    # ------------------------------------------------------------------ ui
    def _build(self) -> None:
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )
        root.add_widget(
            ScreenHeader("Solve from screen", "Read a region of the board and get the steps")
        )

        input_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.INPUT_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.problem_input = labelled_input("x**2 + 3*x - 2 = 0", "type a problem")
        input_row.add_widget(self.problem_input)
        solve_button = Button(
            text="Solve",
            size_hint_x=None,
            width=dp(140),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        solve_button.bind(on_release=lambda _b: self.solve_text(self.problem_input.text))
        input_row.add_widget(solve_button)
        root.add_widget(input_row)

        capture_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        capture_button = Button(
            text="Capture & solve from the screen",
            size_hint_x=None,
            width=dp(320),
            background_normal="",
            background_color=theme.ACCENT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        capture_button.bind(on_release=lambda _b: self.capture_and_solve())
        capture_row.add_widget(capture_button)
        self.status_label = Label(
            text="",
            color=theme.TEXT_MUTED,
            font_size=theme.sp_size(14),
            halign="left",
            valign="middle",
        )
        self.status_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        capture_row.add_widget(self.status_label)
        root.add_widget(capture_row)

        # the escape hatch: an editable box when the OCR is not sure
        self.manual_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.INPUT_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.manual_input = labelled_input("", "check the reading and correct it")
        self.manual_box.add_widget(self.manual_input)
        manual_button = Button(
            text="Solve this",
            size_hint_x=None,
            width=dp(160),
            background_normal="",
            background_color=theme.WARNING,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        manual_button.bind(on_release=lambda _b: self.solve_text(self.manual_input.text))
        self.manual_box.add_widget(manual_button)
        root.add_widget(self.manual_box)
        self.manual_box.height = 0
        self.manual_box.opacity = 0

        self.answer_label = Label(
            text="",
            size_hint_y=None,
            height=dp(44),
            font_size=theme.sp_size(17),
            color=theme.ACCENT,
            halign="left",
            valign="middle",
            bold=True,
        )
        self.answer_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        root.add_widget(self.answer_label)

        self.steps_panel = StepsPanel()
        root.add_widget(self.steps_panel)

        actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.visualize_button = Button(
            text="Visualise",
            size_hint_x=None,
            width=dp(200),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        self.visualize_button.bind(on_release=lambda _b: self._visualize())
        actions.add_widget(self.visualize_button)
        back = Button(
            text="Home",
            size_hint_x=None,
            width=dp(140),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        back.bind(on_release=lambda _b: self._go_home())
        actions.add_widget(back)
        root.add_widget(actions)

        self.add_widget(root)

    # ------------------------------------------------------------ the flow
    def capture_and_solve(self) -> None:
        """Take a capture and let the user pick the area."""
        if self.capture_provider is None:
            show_toast("No capture source is available")
            return
        try:
            image = self.capture_provider()
        except Exception as exc:  # noqa: BLE001 - the capture can fail
            show_toast(f"The screen could not be captured: {exc}")
            return
        if image is None:
            show_toast("The screen could not be captured")
            return
        self._capture = image
        self._show_selector()

    def _show_selector(self) -> None:
        from kivy.core.window import Window

        selector = RegionSelector()
        selector.on_confirm = self._on_region_confirmed
        selector.on_cancel = self._on_region_cancelled
        self._selector = selector
        Window.add_widget(selector)

    def _remove_selector(self) -> None:
        from kivy.core.window import Window

        if self._selector is not None:
            Window.remove_widget(self._selector)
            self._selector = None

    def _on_region_confirmed(self, region: tuple[int, int, int, int]) -> None:
        self._remove_selector()
        image = getattr(self, "_capture", None)
        if image is None:
            return
        left, top, right, bottom = region
        cropped = image.crop((left, top, right, bottom))
        self.run_ocr(cropped)

    def _on_region_cancelled(self) -> None:
        self._remove_selector()
        self.status_label.text = "Cancelled."

    def run_ocr(self, image: Any) -> None:
        """Send the image to the background OCR worker."""
        from aieva.core.ocr.worker import OcrWorker

        if self.ocr_worker is None:
            self.ocr_worker = OcrWorker()
        self.status_label.text = "Reading the board in the background..."
        self.manual_box.height = 0
        self.manual_box.opacity = 0

        def on_result(result: Any) -> None:
            # the callback runs in the worker thread - hop back to the UI thread
            Clock.schedule_once(lambda _dt: self._on_ocr_result(result), 0)

        self.ocr_worker.submit(image, on_result)

    def _on_ocr_result(self, result: Any) -> None:
        """The OCR finished."""
        self.status_label.text = result.confidence_note or f"read by {result.engine}"
        if result.needs_manual_input or result.is_empty:
            guess = result.plain or result.latex
            self.manual_input.text = guess
            self.manual_box.height = dp(theme.INPUT_HEIGHT_DP)
            self.manual_box.opacity = 1
            self.answer_label.text = "Please check the reading."
            return
        self.solve_text(result.plain or result.latex)

    # ------------------------------------------------------------- solving
    def solve_text(self, text: str) -> None:
        """Classify and solve a piece of text (in a worker thread)."""
        text = (text or "").strip()
        if not text:
            show_toast("Type or read a problem first")
            return
        self.status_label.text = "Solving..."

        def work() -> Any:
            classification = classify(text)
            return solve_expression(text, classification=classification)

        def on_done(outcome: Any) -> None:
            self.last_expression = text
            self.answer_label.text = outcome.result.answer_text or "(no answer)"
            steps: list[Step] = list(outcome.result.steps)
            self.steps_panel.show_steps(steps, title=outcome.classification.problem_type)
            self.visualize_button.disabled = not outcome.plottable
            for warning in outcome.warnings:
                show_toast(warning)

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, AievaError):
                show_toast(str(exc))
            else:
                show_toast(f"Could not solve that: {exc}")
            self.status_label.text = "Could not solve the problem."

        run_in_background(work, on_done, on_error, name="aieva-solve")

    # -------------------------------------------------------------- actions
    def _visualize(self) -> None:
        if self.on_visualize is None:
            show_toast("No visualisation is available")
            return
        self.on_visualize(self.last_expression, "text")

    def _go_home(self) -> None:
        if self.manager is not None:
            self.manager.current = "home"


__all__ = ["SolverScreen"]
