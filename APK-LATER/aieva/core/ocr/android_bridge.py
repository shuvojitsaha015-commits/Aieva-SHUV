"""The MediaProjection of an Android board (the Java side).

This module is the **only** place where Aieva talks to Android. It is
imported only on the board (it needs ``pyjnius``), so the rest of the
project stays headless and testable.

How it works:

1. the Java helper (:file:`aieva/android/java/AievaProjection.java`) asks
   the board for the permission to read the screen,
2. Android answers with a token (``Intent``),
3. the helper starts a ``VirtualDisplay`` and copies the frames into an
   ``ImageReader``,
4. Python asks for the newest frame and gets a picture.

The permission can only be given by a person - the teacher taps "Allow"
once, after that the projection runs until the app is closed.

> **Honest:** the Java helper has not been run on a physical board yet (no
> board in the build environment). The Python side around it is tested; the
> Java side still has to prove itself on the device.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


class AndroidMediaProjectionBridge:
    """Reads the screen of the board through the Java helper."""

    def __init__(self, helper: Any = None) -> None:
        self._helper = helper
        self._started = False

    # ------------------------------------------------------------ the helper
    @property
    def helper(self) -> Any:
        """The Java helper (it is loaded the first time it is needed)."""
        if self._helper is None:
            self._helper = self._load_helper()
        return self._helper

    @staticmethod
    def _load_helper() -> Any:
        """Load the Java class of the helper."""
        try:  # pragma: no cover - the board only
            from jnius import autoclass

            return autoclass("org.aieva.AievaProjection")
        except Exception as exc:  # noqa: BLE001 - not a board
            LOGGER.info("The Java helper of the projection is not available: %s", exc)
            return None

    # ------------------------------------------------------------------ api
    def available(self) -> bool:
        """Is the screen of the board readable?"""
        helper = self.helper
        if helper is None:
            return False
        try:
            return bool(helper.isAvailable())
        except Exception:  # noqa: BLE001 - the Java side may fail
            return False

    def start(self) -> bool:
        """Ask for the permission and start the projection."""
        helper = self.helper
        if helper is None:
            return False
        try:
            ok = bool(helper.start())
        except Exception as exc:  # noqa: BLE001 - the Java side may fail
            LOGGER.info("The projection could not be started: %s", exc)
            return False
        self._started = ok
        return ok

    def started(self) -> bool:
        """Is the projection running?"""
        if self._started:
            return True
        helper = self.helper
        if helper is None:
            return False
        try:
            return bool(helper.isStarted())
        except Exception:  # noqa: BLE001 - the Java side may fail
            return False

    def grab(self) -> Any:
        """The newest frame of the screen as a :class:`PIL.Image.Image`."""
        helper = self.helper
        if helper is None:
            return None
        try:
            raw = helper.grabFrame()
        except Exception as exc:  # noqa: BLE001 - the Java side may fail
            LOGGER.info("The frame could not be read: %s", exc)
            return None
        if raw is None:
            return None
        return _to_image(raw)

    def stop(self) -> None:
        """Stop the projection."""
        helper = self.helper
        self._started = False
        if helper is None:
            return
        try:
            helper.stop()
        except Exception:  # noqa: BLE001 - the Java side may fail
            pass


def _to_image(raw: Any) -> Any:
    """Turn the bytes of the Java helper into a picture."""
    from io import BytesIO

    from PIL import Image

    if isinstance(raw, (bytes, bytearray)):
        return Image.open(BytesIO(bytes(raw))).convert("RGB")
    return raw


__all__ = ["AndroidMediaProjectionBridge"]
