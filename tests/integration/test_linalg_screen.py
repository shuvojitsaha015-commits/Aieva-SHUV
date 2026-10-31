"""Phase 6: the linear algebra screen (headless)."""

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
    from aieva.ui.screens.linalg import LinearAlgebraScreen

    widget = LinearAlgebraScreen()
    yield widget


def _wait_for(predicate, timeout: float = 10.0) -> bool:
    from kivy.clock import Clock

    deadline = time.time() + timeout
    while time.time() < deadline:
        Clock.tick()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_every_mode_builds_its_controls(screen) -> None:
    screen.set_mode("vectors")
    assert hasattr(screen, "vector_input")
    assert "scale" in screen.sliders

    screen.set_mode("matrix")
    assert hasattr(screen, "matrix_cells")
    assert "rotation" in screen.sliders

    screen.set_mode("eigen")
    assert hasattr(screen, "matrix_cells")
    assert "rotation" not in screen.sliders

    screen.set_mode("system")
    assert hasattr(screen, "system_input")

    screen.set_mode("complex")
    assert hasattr(screen, "complex_input")
    assert "n" in screen.sliders


def test_matrix_size_switches_the_grid(screen) -> None:
    screen.set_mode("matrix")
    assert len(screen.matrix_cells) == 2
    screen.size_spinner.text = "3x3"
    assert len(screen.matrix_cells) == 3


def test_matrix_is_drawn(screen) -> None:
    screen.set_mode("matrix")
    screen.matrix_cells[0][0].text = "2"
    screen.matrix_cells[1][1].text = "3"
    screen.update_plot()
    assert _wait_for(lambda: "det(M)" in screen.info_label.text)
    assert "6" in screen.info_label.text


def test_system_is_drawn(screen) -> None:
    screen.set_mode("system")
    screen.system_input.text = "2x+y=5; x-y=1"
    screen.update_plot()
    assert _wait_for(lambda: "solution" in screen.info_label.text)


def test_complex_is_drawn(screen) -> None:
    screen.set_mode("complex")
    screen.complex_input.text = "3 + 4i"
    screen.complex_operation.text = "roots"
    screen.sliders["n"].value = 3.0
    screen.update_plot()
    assert _wait_for(lambda: "roots:" in screen.info_label.text)


def test_invalid_matrix_entry_shows_a_toast(screen) -> None:
    screen.set_mode("matrix")
    screen.matrix_cells[0][0].text = "abc"
    screen.update_plot()
    assert _wait_for(lambda: screen.info_label.text == "")
