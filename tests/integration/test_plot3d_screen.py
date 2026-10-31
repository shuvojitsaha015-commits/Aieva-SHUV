"""Phase 7: the 3D plot screen and its touch interaction (headless)."""

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
    from aieva.ui.screens.plot3d import Plot3DScreen

    widget = Plot3DScreen()
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


def test_a_surface_is_built(screen) -> None:
    screen.expression_input.text = "z = x**2 + y**2"
    screen.quality_spinner.text = "low"
    screen.update_plot()
    assert _wait_for(lambda: screen.session is not None)
    assert screen.session.spec.dimension == "3d"


def test_a_2d_plot_is_routed(screen) -> None:
    screen.expression_input.text = "y = sin(x)"
    screen.update_plot()
    assert _wait_for(lambda: screen.session is not None)
    assert screen.session.spec.dimension == "2d"


def test_the_sliders_appear_for_a_parameter(screen) -> None:
    screen.expression_input.text = "z = a*sin(x)*cos(y)"
    screen.quality_spinner.text = "low"
    screen.update_plot()
    assert _wait_for(lambda: screen.session is not None)
    assert _wait_for(lambda: "a" in screen.sliders)


def test_the_buttons_rotate_and_zoom(screen) -> None:
    screen.expression_input.text = "z = x**2 + y**2"
    screen.quality_spinner.text = "low"
    screen.update_plot()
    assert _wait_for(lambda: screen.session is not None)

    before = screen.session.azimuth
    screen.view._button("rotate_right")
    assert screen.session.azimuth != before

    screen.view._button("zoom_in")
    assert screen.session.zoom > 1.0

    screen.view._button("reset")
    assert screen.session.zoom == pytest.approx(1.0)


def test_auto_rotate_toggles(screen) -> None:
    screen.expression_input.text = "z = x**2 + y**2"
    screen.quality_spinner.text = "low"
    screen.update_plot()
    assert _wait_for(lambda: screen.session is not None)
    assert screen.view.toggle_auto_rotate() is True
    assert screen.view.toggle_auto_rotate() is False


def test_a_drag_rotates_the_camera(screen) -> None:
    from kivy.input.motionevent import MotionEvent

    screen.expression_input.text = "z = x**2 + y**2"
    screen.quality_spinner.text = "low"
    screen.update_plot()
    assert _wait_for(lambda: screen.session is not None)

    canvas = screen.view.plot_canvas
    before = screen.session.azimuth

    class FakeTouch(MotionEvent):
        def depack(self, args):
            self.sx, self.sy = args[0], args[1]
            super().depack(args)

    touch = FakeTouch("aieva.test", 1, [100, 100])
    touch.grab_current = lambda *args: None
    canvas.on_touch_down(touch)
    touch.x, touch.y = 140, 100
    canvas.on_touch_move(touch)
    canvas.on_touch_up(touch)
    assert screen.session.azimuth != before
