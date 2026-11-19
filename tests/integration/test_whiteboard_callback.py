"""The whiteboard must reach the app - with and without a picture.

The whiteboard widget only says "something changed" - it does not make
a picture on every single touch (that would be slow). The application
makes the picture itself, when the teacher stops writing.

The old code expected a picture in the callback - and the desktop app
crashed with::

    TypeError: _on_canvas_changed() takes 2 positional arguments but 3 were given

These tests keep both paths working.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module", autouse=True)
def _window():
    from kivy.core.window import Window  # noqa: F401

    return Window


class _FakeApp:
    """The part of the application the whiteboard talks to."""

    def __init__(self) -> None:
        from kivy.clock import Clock

        self.published: list[Any] = []
        self.exported = 0
        self._clock = Clock

        from aieva.ui import app as app_module
        from aieva.ui.app import AievaApp

        # The two methods of the app are used without a window.
        self._on_canvas_changed = AievaApp._on_canvas_changed.__get__(self)
        self._publish_canvas = AievaApp._publish_canvas.__get__(self)
        self._canvas_publish = None
        self.CANVAS_PUBLISH_SECONDS = app_module.CANVAS_PUBLISH_SECONDS

    def _export_canvas(self) -> Any:
        self.exported += 1
        return "the picture of the board"


def test_the_callback_works_without_a_picture() -> None:
    """The whiteboard says only "something changed" - no picture."""
    app = _FakeApp()
    app._on_canvas_changed()  # must not raise


def test_the_callback_works_with_a_picture() -> None:
    app = _FakeApp()
    app._on_canvas_changed("the picture")


def test_the_picture_is_made_when_there_is_none() -> None:
    """Without a picture the board is read when the teacher stops."""
    app = _FakeApp()
    app._publish_canvas(None)
    assert app.exported == 1


def test_a_given_picture_is_not_made_again() -> None:
    """A picture that is already there is used as it is."""
    app = _FakeApp()
    app._publish_canvas("the picture")
    assert app.exported == 0


def test_the_picture_reaches_the_folder_of_the_service(tmp_path, monkeypatch) -> None:
    """The board is published as a picture the service can read."""
    from PIL import Image

    from aieva.core.service.canvas import canvas_files
    from aieva.core.service.config import ServiceConfig

    folder = tmp_path / "board"
    monkeypatch.setenv("AIEVA_SERVICE_FOLDER", str(folder))

    app = _FakeApp()
    picture = Image.new("RGBA", (40, 20), (255, 255, 255, 255))
    app._publish_canvas(picture)

    files = canvas_files(ServiceConfig.from_env().folder)
    assert len(files) == 1
    assert Image.open(files[0]).size == (40, 20)


def test_the_whiteboard_calls_the_callback_without_a_picture() -> None:
    """The real widget: the callback gets no argument at all."""
    from aieva.ui.widgets.whiteboard import Whiteboard

    board = Whiteboard(size=(300, 200))
    board.pos = (0, 0)
    received: list[tuple] = []

    def on_change(*args: Any) -> None:
        received.append(args)

    board.on_change = on_change
    board._changed()
    assert received == [()]
