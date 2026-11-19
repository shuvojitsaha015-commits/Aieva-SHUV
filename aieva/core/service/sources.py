"""The capture sources of the background service.

The service needs a picture of the board, over and over again:

* :class:`~aieva.core.ocr.capture.DesktopScreenSource` - the screen of the
  computer (the normal case: Aieva reads the screen of the board);
* :class:`FolderSource` - the newest picture of a folder. The canvas of the
  application is published there, so the service works without a screen
  capture.

Both return the same :class:`~aieva.core.ocr.capture.Capture`, so the rest
of the service does not care where the picture comes from.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from aieva.core.ocr.capture import Capture, DesktopScreenSource, ScreenSource
from aieva.core.ocr.worker import IMAGE_SUFFIXES

LOGGER = logging.getLogger(__name__)


class NothingToCapture(RuntimeError):
    """There was nothing new on the board - that is not an error."""


class FolderSource(ScreenSource):
    """Reads the newest picture of a folder."""

    name = "folder"

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def available(self) -> bool:
        return self.folder.is_dir()

    def pictures(self) -> list[Path]:
        """The pictures of the folder (the newest one last)."""
        if not self.folder.is_dir():
            return []
        return [
            path
            for path in sorted(self.folder.iterdir())
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ]

    def grab(self) -> Capture:
        pictures = self.pictures()
        if not pictures:
            raise NothingToCapture(f"There is no picture in {self.folder}")
        newest = max(pictures, key=lambda path: path.stat().st_mtime)
        try:
            with Image.open(newest) as image:
                loaded = image.convert("RGB")
        except (OSError, ValueError) as exc:
            # a picture that is broken (or still being written) must not stop
            # the service - the next one is used
            LOGGER.info("The picture %s could not be read: %s", newest.name, exc)
            broken = [path for path in pictures if path != newest]
            if not broken:
                raise NothingToCapture(f"There is no picture in {self.folder}") from exc
            return self._grab_from(broken)
        return Capture(
            image=loaded,
            box=(0, 0, loaded.width, loaded.height),
            source=self.name,
            meta={"file": str(newest)},
        )

    def _grab_from(self, pictures: list[Path]) -> Capture:
        # The newest picture of the list that can be read.
        newest = max(pictures, key=lambda path: path.stat().st_mtime)
        try:
            with Image.open(newest) as image:
                loaded = image.convert("RGB")
        except (OSError, ValueError) as exc:
            LOGGER.info("The picture %s could not be read: %s", newest.name, exc)
            others = [path for path in pictures if path != newest]
            if not others:
                raise NothingToCapture(f"There is no picture in {self.folder}") from exc
            return self._grab_from(others)
        return Capture(
            image=loaded,
            box=(0, 0, loaded.width, loaded.height),
            source=self.name,
            meta={"file": str(newest)},
        )


def build_source(config: object) -> ScreenSource | None:
    """The source the configuration asks for (``None`` when nothing works)."""
    source = str(getattr(config, "source", "auto"))
    if source == "desktop":
        return DesktopScreenSource()
    if source == "folder":
        return FolderSource(getattr(config, "folder", "ocr_inbox"))
    desktop = DesktopScreenSource()
    if desktop.available():
        return desktop
    folder = FolderSource(getattr(config, "folder", "ocr_inbox"))
    if folder.available():
        LOGGER.info("The desktop screen is not available - the folder %s is used", folder.folder)
        return folder
    LOGGER.warning("No capture source is available")
    return None


__all__ = ["FolderSource", "NothingToCapture", "build_source"]
