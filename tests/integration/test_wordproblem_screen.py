"""Phase 9: the word problem screen (headless)."""

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
    from aieva.ui.screens.wordproblem import WordProblemScreen

    widget = WordProblemScreen()
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


def test_the_card_is_empty_at_the_start(screen) -> None:
    assert screen.problem is None
    assert screen.confirm_button.disabled


def test_the_local_model_fills_the_card(screen) -> None:
    """Without a server the local model is used."""
    screen.problem_input.text = (
        "A ball is thrown with 20 m/s at 45 degrees. How high does it fly and how far?"
    )
    screen.analyse()
    assert _wait_for(lambda: screen.problem is not None)
    assert screen.problem is not None
    assert screen.problem.problem_type == "kinematic_projectile"
    assert "v0" in screen._value_inputs
    assert not screen.confirm_button.disabled


def test_the_problem_is_solved_and_drawn(screen) -> None:
    screen.problem_input.text = (
        "A ball is thrown with 20 m/s at 45 degrees. How high does it fly and how far?"
    )
    screen.analyse()
    assert _wait_for(lambda: screen.problem is not None)
    screen.solve()
    assert _wait_for(lambda: screen.session is not None)
    assert screen.session is not None
    assert screen.session.solution.values["max_height"] == pytest.approx(10.204, rel=1e-2)
    assert screen.steps_panel.container.children
    assert screen.plot_area.children
    assert screen.slider_panel.rows


def test_an_edited_value_changes_the_answer(screen) -> None:
    screen.problem_input.text = (
        "A ball is thrown with 20 m/s at 45 degrees. How high does it fly and how far?"
    )
    screen.analyse()
    assert _wait_for(lambda: screen.problem is not None)
    screen.solve()
    assert _wait_for(lambda: screen.session is not None)

    screen._value_inputs["v0"].text = "30"
    screen.solve()
    assert _wait_for(lambda: screen.session.solution.values["max_height"] > 15)
    assert screen.session.solution.values["max_height"] == pytest.approx(22.959, rel=1e-2)


def test_the_animation_can_start_and_stop(screen) -> None:
    screen.problem_input.text = (
        "A ball is thrown with 20 m/s at 45 degrees. How high does it fly and how far?"
    )
    screen.analyse()
    assert _wait_for(lambda: screen.problem is not None)
    screen.solve()
    assert _wait_for(lambda: screen.session is not None)
    assert screen._animation_points is not None
    screen.toggle_animation()
    assert screen._animation_event is not None
    screen.toggle_animation()
    assert screen._animation_event is None
