"""The canvas of the board as a picture for the background service.

Aieva is the smartboard application: what the teacher writes on Aieva's own
canvas is published into the folder the service watches. The service then
reads it - **without a screen capture and without any permission**, which is
the reason the product works on every computer.
"""

from __future__ import annotations

from PIL import Image

from aieva.core.service.canvas import (
    CANVAS_PREFIX,
    canvas_files,
    clear_canvases,
    publish_canvas,
)
from aieva.core.service.sources import FolderSource


def _image(size: tuple[int, int] = (120, 80)) -> Image.Image:
    return Image.new("RGB", size, "white")


def test_the_canvas_is_published(tmp_path) -> None:
    target = publish_canvas(tmp_path, _image())
    assert target is not None
    assert target.is_file()
    assert target.name.startswith(CANVAS_PREFIX)
    assert target.suffix == ".png"


def test_the_service_finds_the_published_canvas(tmp_path) -> None:
    publish_canvas(tmp_path, _image())
    source = FolderSource(tmp_path)
    assert source.available() is True
    capture = source.grab()
    assert capture.image.size == (120, 80)
    assert capture.source == "folder"


def test_the_folder_does_not_grow_forever(tmp_path) -> None:
    for _ in range(6):
        publish_canvas(tmp_path, _image())
    files = canvas_files(tmp_path)
    assert len(files) <= 3


def test_the_old_pictures_are_removed(tmp_path) -> None:
    for _ in range(6):
        publish_canvas(tmp_path, _image())
    keep = canvas_files(tmp_path)
    assert keep
    assert keep[-1].is_file()


def test_the_canvases_can_be_cleared(tmp_path) -> None:
    publish_canvas(tmp_path, _image())
    clear_canvases(tmp_path)
    assert canvas_files(tmp_path) == []


def test_a_broken_picture_does_not_break_the_board(tmp_path) -> None:
    class Broken:
        def convert(self, _mode):  # noqa: ANN001 - a broken picture
            raise RuntimeError("no picture")

    assert publish_canvas(tmp_path, Broken()) is None


def test_without_a_folder_there_is_nothing(tmp_path) -> None:
    assert canvas_files(tmp_path / "missing") == []


def test_a_broken_picture_does_not_stop_the_service(tmp_path) -> None:
    """The service skips a picture that cannot be read."""
    (tmp_path / "board-1.png").write_bytes(b"this is not a picture")
    publish_canvas(tmp_path, _image())
    source = FolderSource(tmp_path)
    capture = source.grab()
    assert capture.image.size == (120, 80)


def test_only_broken_pictures_give_nothing(tmp_path) -> None:
    from aieva.core.service.sources import NothingToCapture

    (tmp_path / "board-1.png").write_bytes(b"this is not a picture")
    source = FolderSource(tmp_path)
    try:
        source.grab()
    except NothingToCapture:
        return
    raise AssertionError("a broken picture must not be read")
