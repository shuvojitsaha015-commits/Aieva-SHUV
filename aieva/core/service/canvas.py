"""The canvas of the board as a picture for the service.

**Aieva is the smartboard application.** The teacher writes on Aieva's own
canvas - so Aieva knows exactly what is on the board, without reading the
screen of the operating system.

The canvas is published into the folder the background service watches
(:class:`~aieva.core.service.sources.FolderSource`). The service picks the
newest picture, reads it, solves it and publishes the answer - the same way
it works with a screen capture, but **without any permission and without a
screen capture**. A file in a folder is the same on every device - that is
why the board works the same way on every computer.

The core stays headless - the Kivy canvas is only read by the UI, the
publishing itself is plain Python.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The prefix of the published pictures.
CANVAS_PREFIX = "board-"

#: How many old pictures are kept (the folder must not grow forever).
DEFAULT_KEEP = 3


def canvas_files(folder: str | Path) -> list[Path]:
    """The published pictures of the board (the oldest first)."""
    directory = Path(folder)
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.startswith(CANVAS_PREFIX)
    )


def publish_canvas(folder: str | Path, image: Any, keep: int = DEFAULT_KEEP) -> Path | None:
    """Put the picture of the board into the folder of the service.

    Returns the file that was written (``None`` when the picture could not be
    saved - a nice to have, never a reason to stop the board).
    """
    directory = Path(folder)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{CANVAS_PREFIX}{int(time.time() * 1000)}.png"
        # The file is written first under another name and then moved: the
        # service never reads a half written picture.
        temporary = target.with_name(target.name + ".part")
        image.convert("RGB").save(temporary, format="PNG")
        os.replace(temporary, target)
    except Exception as exc:  # noqa: BLE001 - the board must not break
        LOGGER.info("The canvas could not be published: %s", exc)
        return None
    _prune(directory, keep)
    return target


def _prune(directory: Path, keep: int) -> None:
    """Remove the old pictures (the newest ``keep`` ones stay)."""
    files = canvas_files(directory)
    for path in files[: max(0, len(files) - max(1, keep))]:
        try:
            path.unlink()
        except OSError:
            pass


def clear_canvases(folder: str | Path) -> None:
    """Remove every published picture (the board is clean)."""
    for path in canvas_files(folder):
        try:
            path.unlink()
        except OSError:
            pass


__all__ = [
    "CANVAS_PREFIX",
    "DEFAULT_KEEP",
    "canvas_files",
    "clear_canvases",
    "publish_canvas",
]
