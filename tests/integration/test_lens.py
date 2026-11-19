"""The lens of the board (the Google Lens of the smart board)."""

from __future__ import annotations

import pytest
from PIL import Image

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module", autouse=True)
def _window():
    from kivy.core.window import Window  # noqa: F401

    return Window


def test_the_picture_of_the_board_is_shown() -> None:
    from aieva.ui.widgets.lens import LensOverlay

    overlay = LensOverlay()
    overlay.set_image(Image.new("RGB", (400, 300), "white"))
    assert overlay.picture.source
    assert overlay._picture_size == (400, 300)


def test_the_area_is_taken_over_in_the_pixels_of_the_picture() -> None:
    from aieva.ui.widgets.lens import LensOverlay

    overlay = LensOverlay()
    overlay.set_image(Image.new("RGB", (400, 300), "white"))
    overlay.picture.size = (400, 300)
    overlay.picture.pos = (0, 0)
    overlay.start = (20, 30)
    overlay.current = (220, 130)
    region = overlay.region()
    assert region[2] > region[0]
    assert region[3] > region[1]


def test_the_area_is_confirmed() -> None:
    from aieva.ui.widgets.lens import LensOverlay

    seen: list[tuple[int, int, int, int]] = []
    overlay = LensOverlay()
    overlay.set_image(Image.new("RGB", (400, 300), "white"))
    overlay.picture.size = (400, 300)
    overlay.on_confirm = seen.append
    overlay.start = (20, 30)
    overlay.current = (220, 130)
    overlay._confirm()
    assert seen


def test_a_too_small_area_is_not_confirmed() -> None:
    from aieva.ui.widgets.lens import LensOverlay

    seen: list[tuple[int, int, int, int]] = []
    overlay = LensOverlay()
    overlay.set_image(Image.new("RGB", (400, 300), "white"))
    overlay.picture.size = (400, 300)
    overlay.on_confirm = seen.append
    overlay.start = (20, 30)
    overlay.current = (25, 32)
    overlay._confirm()
    assert seen == []


def test_the_popup_shows_the_reading_and_the_answer() -> None:
    from aieva.ui.widgets.lens import LensResult

    popup = LensResult()
    popup.show(
        reading="2*x + 3 = 7",
        answer="x = 2",
        steps=[{"text": "Subtract 3 from both sides."}],
        plot="",
        note="read in 120 ms",
    )
    assert popup.reading_label.text == "2*x + 3 = 7"
    assert popup.answer_label.text == "x = 2"
    assert "Subtract 3" in popup.steps.text
    assert "120 ms" in popup.note.text


def test_the_popup_can_be_closed() -> None:
    from aieva.ui.widgets.lens import LensResult

    closed: list[bool] = []
    popup = LensResult()
    popup.on_close = lambda: closed.append(True)
    popup._close()
    assert closed == [True]


def test_the_reading_can_be_opened_in_the_app() -> None:
    from aieva.ui.widgets.lens import LensResult

    opened: list[str] = []
    popup = LensResult()
    popup.on_open = opened.append
    popup.show(reading="x = 2")
    popup._open()
    assert opened == ["x = 2"]
