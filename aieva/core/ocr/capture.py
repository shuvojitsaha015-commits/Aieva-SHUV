"""The screen capture sources.

A :class:`ScreenSource` knows how to grab the current screen:

* :class:`CanvasSource` - the whiteboard canvas of the application;
* :class:`DesktopScreenSource` - the desktop screen via ``PIL.ImageGrab``
  (development on a laptop);

Every source returns a :class:`Capture` with the image and the pixel
coordinates of the captured area, so a region can be cut out of it.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

LOGGER = logging.getLogger(__name__)


@dataclass
class Capture:
    """A grabbed area of a screen."""

    image: Image.Image
    #: The rectangle in the coordinate system of the source.
    box: tuple[int, int, int, int] = (0, 0, 0, 0)
    source: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def crop(self, region: tuple[int, int, int, int] | None) -> Capture:
        """Cut a region out of the capture (the coordinates are local)."""
        if region is None:
            return self
        left, top, right, bottom = (int(value) for value in region)
        left = max(left, 0)
        top = max(top, 0)
        right = min(right, self.image.width)
        bottom = min(bottom, self.image.height)
        if right <= left or bottom <= top:
            return self
        return Capture(
            image=self.image.crop((left, top, right, bottom)),
            box=self.box,
            source=self.source,
            meta=dict(self.meta),
        )


class ScreenSource(ABC):
    """The interface of a capture source."""

    name: str = "source"

    @abstractmethod
    def grab(self) -> Capture:
        """Take a screenshot."""

    def available(self) -> bool:
        """``True`` when the source can be used right now."""
        return True


class CanvasSource(ScreenSource):
    """Captures the whiteboard canvas.

    The whiteboard widget stores its strokes as data, so the capture is a
    rendering of those strokes - it works on every platform.
    """

    name = "canvas"

    def __init__(self, whiteboard: Any = None) -> None:
        self.whiteboard = whiteboard

    def available(self) -> bool:
        return self.whiteboard is not None

    def grab(self) -> Capture:
        if self.whiteboard is None:
            raise RuntimeError("No whiteboard to capture")
        image = self.whiteboard.export_to_image()
        return Capture(image=image, box=(0, 0, image.width, image.height), source=self.name)


class DesktopScreenSource(ScreenSource):
    """Captures the desktop screen (development only)."""

    name = "desktop"

    def __init__(self, all_screens: bool = False) -> None:
        self.all_screens = all_screens

    def available(self) -> bool:
        try:
            from PIL import ImageGrab  # noqa: F401
        except Exception:  # noqa: BLE001 - Pillow is built without ImageGrab
            return False
        return True

    def grab(self) -> Capture:
        from PIL import ImageGrab

        try:
            image = ImageGrab.grab(all_screens=self.all_screens)
        except Exception as exc:  # noqa: BLE001 - no display on the server
            raise RuntimeError(f"The desktop screen could not be captured: {exc}") from exc
        return Capture(
            image=image.convert("RGB"),
            box=(0, 0, image.width, image.height),
            source=self.name,
        )


def default_sources(whiteboard: Any = None) -> list[ScreenSource]:
    """The capture sources in the order they should be tried."""
    sources: list[ScreenSource] = []
    desktop = DesktopScreenSource()
    if desktop.available():
        sources.append(desktop)
    if whiteboard is not None:
        sources.append(CanvasSource(whiteboard))
    return sources


__all__ = [
    "CanvasSource",
    "Capture",
    "DesktopScreenSource",
    "ScreenSource",
    "default_sources",
]
