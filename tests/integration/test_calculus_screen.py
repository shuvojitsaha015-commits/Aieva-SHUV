"""Phase 5: the calculus screen (headless)."""

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
    from aieva.ui.screens.calculus import CalculusScreen

    widget = CalculusScreen()
    yield widget
    widget.stop_animation()


def _wait_for(predicate, timeout: float = 10.0) -> bool:
    from kivy.clock import Clock

    deadline = time.time() + timeout
    while time.time() < deadline:
        Clock.tick()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_modes_build_the_right_controls(screen) -> None:
    screen.set_mode("integral")
    assert "a" in screen.sliders and "b" in screen.sliders

    screen.set_mode("riemann")
    assert "n" in screen.sliders
    assert hasattr(screen, "method_spinner")

    screen.set_mode("tangent")
    assert "x0" in screen.sliders
    assert hasattr(screen, "play_button")

    screen.set_mode("area_between")
    assert screen.second_input.disabled is False

    screen.set_mode("integral")
    assert screen.second_input.disabled is True


def test_integral_is_drawn(screen) -> None:
    screen.set_mode("integral")
    screen.function_input.text = "sin(x)"
    screen.sliders["a"].value = 0.0
    screen.sliders["b"].value = 3.14159
    screen.update_plot()
    assert _wait_for(lambda: "exact" in screen.info_label.text)
    assert "2" in screen.info_label.text


def test_riemann_is_drawn(screen) -> None:
    screen.set_mode("riemann")
    screen.function_input.text = "x**2"
    screen.sliders["a"].value = 0.0
    screen.sliders["b"].value = 1.0
    screen.method_spinner.text = "midpoint"
    screen.update_plot()
    assert _wait_for(lambda: "sum" in screen.info_label.text)


def test_tangent_animation_can_be_started_and_stopped(screen) -> None:
    screen.set_mode("tangent")
    screen.function_input.text = "sin(x)"
    screen.update_plot()
    assert _wait_for(lambda: screen.session is not None)

    screen.toggle_animation()
    assert screen._animation_event is not None
    assert screen.play_button.text == "Pause"
    screen.toggle_animation()
    assert screen._animation_event is None
    assert screen.play_button.text == "Play"
