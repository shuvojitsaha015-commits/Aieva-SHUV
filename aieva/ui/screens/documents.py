"""The **Documents** screen (Phase 10).

The user picks a PDF, a PPTX or a DOCX; the document is read in a worker
thread and every equation is shown in a list. A tap sends the equation to the
solver or to the plot - the pictures go through the OCR pipeline (also in a
worker thread).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner

from aieva.core.docs_parser.extract import (
    EquationCandidate,
    document_kind,
    extract_equations,
    page_count,
    unsupported_message,
)
from aieva.core.errors import AievaError
from aieva.ui import theme
from aieva.ui.widgets.header import ScreenHeader
from aieva.ui.widgets.toast import show_toast
from aieva.ui.workers import run_in_background

LOGGER = logging.getLogger(__name__)

#: The page limits the user can choose.
PAGE_LIMITS: tuple[str, ...] = ("5", "10", "20", "all")


class DocumentsScreen(Screen):
    """Read a document and pick an equation out of it."""

    #: Called with ``(text, kind)`` when the user wants to plot an equation.
    on_plot_requested: Callable[[str, str], None] | None = None
    #: Called with ``(text,)`` when the user wants to solve an equation.
    on_solve_requested: Callable[[str], None] | None = None
    #: The OCR pipeline that reads the pictures of a document.
    ocr_pipeline: Any = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = "documents"
        self.candidates: list[EquationCandidate] = []
        self.current_path: Path | None = None
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )
        root.add_widget(
            ScreenHeader("Documents", "The equations of a PDF, a presentation or a Word file")
        )

        # --- the top row: the path and the actions -----------------------
        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.path_label = Label(
            text="Pick a PDF, PPTX or DOCX file",
            color=theme.TEXT_MUTED,
            font_size=theme.sp_size(15),
            halign="left",
            valign="middle",
        )
        self.path_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        top.add_widget(self.path_label)

        self.limit_spinner = Spinner(
            text="all",
            values=list(PAGE_LIMITS),
            size_hint_x=None,
            width=dp(120),
            height=dp(44),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
        )
        top.add_widget(self.limit_spinner)

        open_button = Button(
            text="Read the document",
            size_hint_x=None,
            width=dp(220),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        open_button.bind(on_release=lambda _b: self.read_document())
        top.add_widget(open_button)

        home_button = Button(
            text="Home",
            size_hint_x=None,
            width=dp(130),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        home_button.bind(on_release=lambda _b: self._go_home())
        top.add_widget(home_button)
        root.add_widget(top)

        # --- the file chooser and the results ---------------------------
        middle = BoxLayout(orientation="horizontal", spacing=dp(theme.GAP_DP))

        self.chooser = FileChooserListView(
            path=str(Path.home()),
            filters=["*.pdf", "*.pptx", "*.docx", "*.doc", "*.ppt"],
            show_hidden=False,
            dirselect=False,
        )
        self.chooser.bind(selection=self._on_selection)
        middle.add_widget(self.chooser)

        result_box = BoxLayout(orientation="vertical", spacing=dp(theme.GAP_DP))
        self.status_label = Label(
            text="",
            size_hint_y=None,
            height=dp(30),
            color=theme.TEXT_MUTED,
            font_size=theme.sp_size(14),
            halign="left",
            valign="middle",
        )
        self.status_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        result_box.add_widget(self.status_label)

        self.result_list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.result_list.bind(minimum_height=self.result_list.setter("height"))
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(8))
        scroll.add_widget(self.result_list)
        result_box.add_widget(scroll)
        middle.add_widget(result_box)
        root.add_widget(middle)

        # --- the actions on the selected equation -----------------------
        actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        solve_button = Button(
            text="Solve it",
            size_hint_x=None,
            width=dp(170),
            background_normal="",
            background_color=theme.ACCENT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        solve_button.bind(on_release=lambda _b: self._on_solve())
        actions.add_widget(solve_button)

        plot_button = Button(
            text="Plot it",
            size_hint_x=None,
            width=dp(170),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        plot_button.bind(on_release=lambda _b: self._on_plot())
        actions.add_widget(plot_button)

        self.selected_label = Label(
            text="",
            color=theme.TEXT_MUTED,
            font_size=theme.sp_size(14),
            halign="left",
            valign="middle",
        )
        self.selected_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        actions.add_widget(self.selected_label)
        root.add_widget(actions)

        self.add_widget(root)
        self.selected: EquationCandidate | None = None
        self._show_results([])

    # ------------------------------------------------------------- the files
    def _on_selection(self, _chooser: Any, selection: list[str]) -> None:
        """The user picked a file in the chooser."""
        if not selection:
            return
        path = Path(selection[0])
        self.path_label.text = str(path)
        kind = document_kind(path)
        if kind == "unsupported":
            self.status_label.text = unsupported_message(path)
            self._show_results([])
            return
        pages = page_count(path)
        self.status_label.text = f"{path.name} - {pages} page(s)"

    def read_document(self) -> None:
        """Read the selected document (in a worker thread)."""
        selection = list(self.chooser.selection)
        if not selection:
            show_toast("Pick a document first")
            return
        path = Path(selection[0])
        kind = document_kind(path)
        if kind == "unsupported":
            show_toast(unsupported_message(path))
            self.status_label.text = unsupported_message(path)
            return

        limit = self.limit_spinner.text
        max_pages = 0 if limit == "all" else int(limit)
        self.status_label.text = f"Reading {path.name}..."

        def work() -> list[EquationCandidate]:
            return extract_equations(path, max_pages=max_pages)

        def on_done(candidates: list[EquationCandidate]) -> None:
            self.current_path = path
            self.candidates = list(candidates)
            self._show_results(self.candidates)
            pages = page_count(path)
            self.status_label.text = (
                f"{path.name}: {len(candidates)} equation(s) in {pages} page(s)"
            )

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, AievaError):
                show_toast(str(exc))
            else:
                show_toast(f"The document could not be read: {exc}")
            self.status_label.text = "The document could not be read."

        run_in_background(work, on_done, on_error, name="aieva-documents")

    # ------------------------------------------------------------ the results
    def _show_results(self, candidates: list[EquationCandidate]) -> None:
        """Show every equation of the document."""
        self.result_list.clear_widgets()
        self.selected = None
        if not candidates:
            label = Label(
                text="No equation found yet.",
                size_hint_y=None,
                height=dp(36),
                font_size=theme.sp_size(14),
                color=theme.TEXT_MUTED,
                halign="left",
                valign="middle",
            )
            label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            self.result_list.add_widget(label)
            return
        for candidate in candidates:
            button = Button(
                text=f"p{candidate.page}  {candidate.display}",
                size_hint_y=None,
                height=dp(theme.BUTTON_HEIGHT_DP),
                background_normal="",
                background_color=theme.SURFACE,
                color=theme.TEXT,
                font_size=theme.sp_size(14),
                halign="left",
            )
            button.bind(on_release=lambda _b, item=candidate: self._on_candidate(item))
            self.result_list.add_widget(button)

    def _on_candidate(self, candidate: EquationCandidate) -> None:
        """The user tapped an equation."""
        self.selected = candidate
        self.selected_label.text = f"page {candidate.page}: {candidate.display}"
        if candidate.needs_ocr:
            self._read_picture(candidate)

    def _read_picture(self, candidate: EquationCandidate) -> None:
        """Send the picture of a candidate to the OCR (in the background)."""
        self.status_label.text = "Reading the picture..."
        pipeline = self.ocr_pipeline
        if pipeline is None:
            from aieva.core.ocr.pipeline import OcrPipeline

            pipeline = OcrPipeline()
        image = candidate.image

        def work() -> Any:
            return pipeline.run(image)

        def on_done(result: Any) -> None:
            if result.needs_manual_input:
                show_toast("The picture could not be read - please type the equation")
                self.status_label.text = "The picture could not be read."
                return
            candidate.latex = result.latex
            candidate.text = result.plain or result.latex
            self.selected_label.text = f"page {candidate.page}: {candidate.display}"
            self.status_label.text = "The picture was read."

        def on_error(exc: BaseException) -> None:
            LOGGER.info("The picture could not be read: %s", exc)
            show_toast(f"The picture could not be read: {exc}")
            self.status_label.text = "The picture could not be read."

        run_in_background(work, on_done, on_error, name="aieva-documents-ocr")

    # ------------------------------------------------------------- the actions
    def _on_solve(self) -> None:
        """Send the selected equation to the solver."""
        text = self._selected_text()
        if not text:
            show_toast("Pick an equation first")
            return
        if self.on_solve_requested is not None:
            self.on_solve_requested(text)

    def _on_plot(self) -> None:
        """Send the selected equation to the plot."""
        text = self._selected_text()
        if not text:
            show_toast("Pick an equation first")
            return
        if self.on_plot_requested is not None:
            self.on_plot_requested(text, "text")

    def _selected_text(self) -> str:
        """The text of the selected candidate (LaTeX first)."""
        candidate = self.selected
        if candidate is None:
            return ""
        if candidate.has_latex:
            return candidate.latex or ""
        return candidate.text

    def _go_home(self) -> None:
        if self.manager is not None:
            self.manager.current = "home"


__all__ = ["PAGE_LIMITS", "DocumentsScreen"]
