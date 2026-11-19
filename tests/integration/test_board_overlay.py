"""The floating control above the board (the control of the service)."""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module", autouse=True)
def _window():
    from kivy.core.window import Window  # noqa: F401

    return Window


def _app(tmp_path):
    from aieva.ui.board_overlay import build_overlay_app

    application = build_overlay_app()(state_file=tmp_path / "service_state.json")
    application.build()
    return application


def test_the_control_has_a_scan_and_a_drag_button(tmp_path) -> None:
    application = _app(tmp_path)
    assert application.scan_button.text == "Scan"
    assert application.drag_button.text == "Drag"


def test_the_scan_button_asks_the_service(tmp_path) -> None:
    application = _app(tmp_path)
    application._ask_for_scan()
    assert application.request_file.is_file()
    payload = json.loads(application.request_file.read_text(encoding="utf-8"))
    assert "at" in payload


def test_a_result_is_shown(tmp_path) -> None:
    application = _app(tmp_path)
    application._show(
        {
            "plain": "2*x + 3 = 7",
            "latex": "2*x + 3 = 7",
            "answer": "x = 2",
            "created_at": 1.0,
        }
    )
    assert "2·x + 3 = 7" in application.reading.text
    assert application.answer.text == "x = 2"
    assert application.scan_button.text == "Scan"


def test_the_explanation_is_shown(tmp_path) -> None:
    application = _app(tmp_path)
    application._show(
        {
            "plain": "2*x + 3 = 7",
            "answer": "x = 2",
            "steps": [{"text": "Move the 3 to the other side."}, {"text": "Divide by 2."}],
            "created_at": 1.0,
        }
    )
    assert "Move the 3" in application.steps.text
    assert "Divide by 2" in application.steps.text


def test_the_window_collapses_again(tmp_path) -> None:
    application = _app(tmp_path)
    application._show({"plain": "x = 2", "answer": "2", "created_at": 1.0})
    application._collapse()
    assert application.card.height == 0


def test_the_control_sits_on_the_left_edge_in_the_middle() -> None:
    from aieva.ui.board_overlay import CONTROL_SIZE, control_position

    left, top = control_position((1920, 1080))
    assert left == 18, "the control is on the left edge"
    # the middle of the screen is 540 - the control is centred on it
    assert abs((top - CONTROL_SIZE[1] / 2) - 540) < 2


def test_the_popup_goes_next_to_the_problem() -> None:
    from aieva.ui.board_overlay import POPUP_SIZE, popup_position

    # the problem is in the middle of the screen
    region = (700, 400, 1100, 600)
    left, top = popup_position((1920, 1080), region=region)
    assert left >= 1100, "the popup is right of the problem"
    assert left + POPUP_SIZE[0] <= 1920


def test_the_popup_stays_on_the_screen() -> None:
    from aieva.ui.board_overlay import POPUP_SIZE, popup_position

    # the problem is at the very right - the popup has to move to the left
    region = (1700, 100, 1900, 300)
    left, top = popup_position((1920, 1080), region=region)
    assert left >= 0
    assert left + POPUP_SIZE[0] <= 1920
    assert top >= 0


def test_the_popup_without_a_region_goes_to_the_edge() -> None:
    from aieva.ui.board_overlay import popup_position

    left, _top = popup_position((1920, 1080), region=None)
    assert left == 18


def test_the_steps_are_formatted() -> None:
    from aieva.ui.board_overlay import steps_text

    text = steps_text([{"text": "First."}, {"explanation": "Second."}, {"latex": "x = 2"}])
    assert text.startswith("1. First.")
    assert "2. Second." in text
    assert "3. x = 2" in text
    assert steps_text(None) == ""
