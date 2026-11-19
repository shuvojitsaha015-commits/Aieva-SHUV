"""The Android MediaProjection - PARKED, not part of the application.

This file is the copy of the screen capture that was written for an Android
board. It is **not** used by Aieva (the application is a Windows program) and
nothing in ``aieva/`` imports it. It is kept here so the idea is not lost.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from aieva.core.ocr.capture import Capture, ScreenSource

class MediaProjectionBridge:
    """The Java side of the Android screen capture.

    The class is the *interface* between Python and the Android system. The
    real implementation lives in :func:`build_android_bridge` (it needs
    ``pyjnius`` and runs only on the board); a test can hand over any object
    with the same methods.
    """

    def available(self) -> bool:
        """Can the screen be captured at all?"""
        return False

    def start(self) -> bool:
        """Ask for the permission and start the projection."""
        return False

    def started(self) -> bool:
        """Is the projection running?"""
        return False

    def grab(self) -> Image.Image | None:
        """The picture of the screen (``None`` when it does not work)."""
        return None

    def stop(self) -> None:
        """Stop the projection."""
        return None


class AndroidProjectionSource(ScreenSource):
    """The screen of an Android smart board (MediaProjection).

    This is the capture of the content of **other** applications of the
    board - a PDF that is open, for example. The writing that happens on
    Aieva's own canvas does not need it (see
    :mod:`aieva.core.service.canvas`).

    The class only talks to a :class:`MediaProjectionBridge`, so it can be
    tested without a board.
    """

    name = "android"

    def __init__(self, bridge: Any = None, service: Any = None) -> None:
        self.bridge = bridge
        self.service = service

    def _the_bridge(self) -> Any:
        if self.bridge is None:
            self.bridge = build_android_bridge()
        return self.bridge

    def available(self) -> bool:
        bridge = self._the_bridge()
        if bridge is None:
            return False
        try:
            return bool(bridge.available())
        except Exception:  # noqa: BLE001 - the Java side may fail
            return False

    def grab(self) -> Capture:
        bridge = self._the_bridge()
        if bridge is None:
            raise RuntimeError(
                "The Android screen projection is not available - use the "
                "canvas of Aieva or import a screenshot."
            )
        try:
            if not bridge.started() and not bridge.start():
                raise RuntimeError(
                    "The Android screen projection was not allowed - the board "
                    "needs the permission for the screen capture."
                )
            image = bridge.grab()
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001 - the Java side may fail
            raise RuntimeError(f"The screen of the board could not be read: {exc}") from exc
        if image is None:
            raise RuntimeError("The screen of the board could not be read")
        loaded = image.convert("RGB")
        return Capture(
            image=loaded,
            box=(0, 0, loaded.width, loaded.height),
            source=self.name,
        )

    def stop(self) -> None:
        """Stop the projection (the permission is asked again next time)."""
        bridge = self._the_bridge()
        if bridge is not None:
            try:
                bridge.stop()
            except Exception:  # noqa: BLE001 - the Java side may fail
                pass


def build_android_bridge() -> MediaProjectionBridge | None:
    """The real MediaProjection (only on the board, needs ``pyjnius``).

    On every other system ``None`` is returned - the source then says that
    it is not available instead of crashing.
    """
    try:  # pragma: no cover - the board only
        from jnius import autoclass  # noqa: F401
    except Exception:  # noqa: BLE001 - not Android
        return None
    try:  # pragma: no cover - the board only
        from aieva.core.ocr.android_bridge import AndroidMediaProjectionBridge

        bridge = AndroidMediaProjectionBridge()
        return bridge if bridge.available() else None
    except Exception:  # noqa: BLE001 - the Java helper may be missing
        return None



__all__ = [
    "AndroidProjectionSource",
    "MediaProjectionBridge",
    "build_android_bridge",
]
