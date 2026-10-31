"""Phase 8: the "Solve from Screen" screen (headless)."""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module", autouse=True)
def _window():
    from kivy.core.window import Window  # noqa: F401

    return Window


@pytest.fixture
def screen():
    from aieva.ui.screens.solver import SolverScreen

    widget = SolverScreen()
    yield widget


def _wait_for(predicate, timeout: float = 15.0) -> bool:
    from kivy.clock import Clock

    deadline = time.time() + timeout
    while time.time() < deadline:
        Clock.tick()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_a_typed_problem_is_solved(screen) -> None:
    screen.problem_input.text = "2*x + 3 = 7"
    screen.solve_text(screen.problem_input.text)
    assert _wait_for(lambda: "2" in screen.answer_label.text)
    assert screen.steps_panel.container.children


def test_the_steps_are_shown(screen) -> None:
    screen.solve_text("x**2 - 4 = 0")
    assert _wait_for(lambda: len(screen.steps_panel.container.children) >= 2)


def test_the_ocr_runs_in_the_background(screen, monkeypatch, tmp_path) -> None:
    from PIL import Image

    from aieva.core.ocr.engines import MockOcr
    from aieva.core.ocr.pipeline import OcrPipeline
    from aieva.core.ocr.worker import OcrWorker

    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    from aieva.config import get_settings

    get_settings(reload=True)
    screen.ocr_worker = OcrWorker(
        pipeline=OcrPipeline(engines=[MockOcr(latex="2*x + 3 = 7", plain="2*x + 3 = 7")])
    )
    screen.run_ocr(Image.new("RGB", (60, 30), "white"))
    assert _wait_for(lambda: "2" in screen.answer_label.text)


def test_a_bad_reading_asks_the_user(screen, monkeypatch, tmp_path) -> None:
    from PIL import Image

    from aieva.core.ocr.engines import MockOcr
    from aieva.core.ocr.pipeline import OcrPipeline
    from aieva.core.ocr.worker import OcrWorker

    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    from aieva.config import get_settings

    get_settings(reload=True)
    screen.ocr_worker = OcrWorker(
        pipeline=OcrPipeline(engines=[MockOcr(latex="\\bad", plain="??")])
    )
    screen.run_ocr(Image.new("RGB", (60, 30), "white"))
    assert _wait_for(lambda: screen.manual_box.height > 0)
    assert screen.manual_input.text == "??"


def test_the_region_selector_returns_a_rectangle(screen) -> None:
    from aieva.ui.widgets.region_selector import RegionSelector

    selector = RegionSelector()
    selector.start = (10, 20)
    selector.current = (110, 90)
    assert selector.region() == (10, 20, 110, 90)
