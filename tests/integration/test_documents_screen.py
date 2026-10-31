"""Phase 10: the documents screen (headless)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

DOCS = Path(__file__).resolve().parents[1] / "fixtures" / "docs"


@pytest.fixture(scope="module", autouse=True)
def _window():
    from kivy.core.window import Window  # noqa: F401

    return Window


@pytest.fixture
def screen():
    from aieva.ui.screens.documents import DocumentsScreen

    widget = DocumentsScreen()
    yield widget


def _wait_for(predicate, timeout: float = 20.0) -> bool:
    from kivy.clock import Clock

    deadline = time.time() + timeout
    while time.time() < deadline:
        Clock.tick()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_the_screen_starts_empty(screen) -> None:
    assert screen.candidates == []
    assert screen.selected is None


def test_a_docx_is_read_and_the_equations_are_shown(screen) -> None:
    screen.chooser.selection = [str(DOCS / "equations.docx")]
    screen.read_document()
    assert _wait_for(lambda: len(screen.candidates) == 2)
    assert len(screen.result_list.children) == 2


def test_a_tap_selects_the_equation(screen) -> None:
    screen.chooser.selection = [str(DOCS / "equations.docx")]
    screen.read_document()
    assert _wait_for(lambda: len(screen.candidates) == 2)
    screen._on_candidate(screen.candidates[0])
    assert screen.selected is screen.candidates[0]
    assert screen._selected_text()


def test_the_equation_goes_to_the_solver(screen) -> None:
    seen: list[str] = []
    screen.on_solve_requested = seen.append
    screen.chooser.selection = [str(DOCS / "equations.docx")]
    screen.read_document()
    assert _wait_for(lambda: len(screen.candidates) == 2)
    screen._on_candidate(screen.candidates[0])
    screen._on_solve()
    assert seen and "x^{2}" in seen[0]


def test_the_equation_goes_to_the_plot(screen) -> None:
    seen: list[tuple[str, str]] = []
    screen.on_plot_requested = lambda text, kind: seen.append((text, kind))
    screen.chooser.selection = [str(DOCS / "text.pdf")]
    screen.read_document()
    assert _wait_for(lambda: len(screen.candidates) >= 2)
    screen._on_candidate(screen.candidates[0])
    screen._on_plot()
    assert seen and seen[0][1] == "text"


def test_an_old_format_gets_a_clear_message(screen, tmp_path) -> None:
    old = tmp_path / "lesson.doc"
    old.write_bytes(b"legacy")
    screen.chooser.selection = [str(old)]
    screen._on_selection(screen.chooser, [str(old)])
    assert "docx" in screen.status_label.text


def test_the_picture_of_a_pptx_goes_to_the_ocr(screen) -> None:
    from aieva.core.ocr.engines import MockOcr
    from aieva.core.ocr.pipeline import OcrPipeline

    screen.ocr_pipeline = OcrPipeline(
        engines=[MockOcr(latex="x^2 + 3x - 2 = 0", plain="x**2 + 3*x - 2")]
    )
    screen.chooser.selection = [str(DOCS / "slide.pptx")]
    screen.read_document()
    assert _wait_for(lambda: len(screen.candidates) == 2)
    picture = [item for item in screen.candidates if item.needs_ocr]
    assert picture
    screen._on_candidate(picture[0])
    assert _wait_for(lambda: picture[0].has_latex)
    assert "x" in picture[0].latex
