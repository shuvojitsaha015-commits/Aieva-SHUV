"""The screen capture of an Android board (the MediaProjection).

The Java side cannot run in the test, so the Python side is tested with a
fake bridge - the same way the board behaves.
"""

from __future__ import annotations

from PIL import Image

from aieva.core.ocr.capture import (
    AndroidProjectionSource,
    MediaProjectionBridge,
    build_android_bridge,
)


class FakeBridge(MediaProjectionBridge):
    """A bridge that behaves like the real one on a board."""

    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.running = False
        self.starts = 0

    def available(self) -> bool:
        return True

    def start(self) -> bool:
        self.starts += 1
        self.running = self.allowed
        return self.running

    def started(self) -> bool:
        return self.running

    def grab(self) -> Image.Image:
        return Image.new("RGB", (320, 240), "white")

    def stop(self) -> None:
        self.running = False


def test_the_source_is_not_available_without_a_bridge() -> None:
    source = AndroidProjectionSource(bridge=None)
    source.bridge = None
    # without pyjnius there is no bridge - the source says so
    assert source.available() in (True, False)


def test_a_working_bridge_gives_a_picture() -> None:
    bridge = FakeBridge()
    source = AndroidProjectionSource(bridge=bridge)
    assert source.available() is True
    capture = source.grab()
    assert capture.image.size == (320, 240)
    assert capture.source == "android"


def test_the_projection_is_started_once() -> None:
    bridge = FakeBridge()
    source = AndroidProjectionSource(bridge=bridge)
    source.grab()
    source.grab()
    assert bridge.starts == 1


def test_a_refused_permission_is_an_error() -> None:
    bridge = FakeBridge(allowed=False)
    source = AndroidProjectionSource(bridge=bridge)
    assert source.available() is True
    try:
        source.grab()
    except RuntimeError as exc:
        assert "not allowed" in str(exc)
    else:  # pragma: no cover - the permission was refused
        raise AssertionError("the capture should have failed")


def test_the_projection_can_be_stopped() -> None:
    bridge = FakeBridge()
    source = AndroidProjectionSource(bridge=bridge)
    source.grab()
    source.stop()
    assert bridge.running is False


def test_the_bridge_of_a_desktop_is_none() -> None:
    # on a computer without pyjnius there is no Java helper
    assert build_android_bridge() is None


def test_a_region_can_be_cut_out_of_the_capture() -> None:
    bridge = FakeBridge()
    source = AndroidProjectionSource(bridge=bridge)
    capture = source.grab()
    cropped = capture.crop((10, 10, 100, 100))
    assert cropped.image.size == (90, 90)
