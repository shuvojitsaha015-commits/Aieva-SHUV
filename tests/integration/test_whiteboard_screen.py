"""The whiteboard screen of the smart board (Aieva IS the board)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module", autouse=True)
def _window():
    from kivy.core.window import Window  # noqa: F401

    return Window


@pytest.fixture
def screen():
    from aieva.ui.screens.whiteboard import WhiteboardScreen

    widget = WhiteboardScreen()
    yield widget


def test_the_board_has_a_read_button(screen) -> None:
    labels = [button.text for button in screen.walk() if hasattr(button, "text")]
    assert "Read the board" in labels


def test_the_read_button_gives_the_picture_of_the_board(screen) -> None:
    seen: list[object] = []
    screen.on_request_read = seen.append
    screen._request_read()
    assert seen
    assert seen[0].size[0] > 0


def test_the_writing_is_announced(screen) -> None:
    """Every change of the writing reaches the application."""
    changes: list[object] = []
    screen.on_canvas_changed = changes.append
    screen.notify_change()
    assert changes


def test_the_canvas_is_notified_when_a_stroke_ends(screen) -> None:
    changes: list[int] = []
    screen.on_canvas_changed = lambda image: changes.append(1)
    screen.whiteboard.strokes.append(_stroke(screen))
    screen.whiteboard._changed()
    assert changes == [1]


def _stroke(screen):
    from aieva.ui.widgets.whiteboard import Stroke

    return Stroke(points=[0, 0, 10, 10], color=(0, 0, 0, 1), width=4)
