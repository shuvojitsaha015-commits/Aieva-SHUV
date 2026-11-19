"""The key that reads the board on the spot."""

from __future__ import annotations

import threading
import time

from aieva.core.service.hotkey import DEFAULT_KEYS, HotkeyWatcher


def test_the_key_is_f8_by_default() -> None:
    assert DEFAULT_KEYS == ("f8",)


def test_the_watcher_starts_and_stops() -> None:
    watcher = HotkeyWatcher(lambda: None)
    watcher.start()
    assert watcher.is_running is True
    watcher.stop()
    assert watcher.is_running is False


def test_the_watcher_can_be_started_twice() -> None:
    watcher = HotkeyWatcher(lambda: None)
    watcher.start()
    watcher.start()
    assert watcher.is_running is True
    watcher.stop()


def test_the_callback_is_called() -> None:
    seen = threading.Event()
    watcher = HotkeyWatcher(lambda: seen.set(), keys=("f8",))
    watcher._fire()
    assert seen.is_set()


def test_a_broken_callback_does_not_kill_the_watcher() -> None:
    def broken() -> None:
        raise RuntimeError("the listener is broken")

    watcher = HotkeyWatcher(broken)
    watcher._fire()
    assert watcher.callback is broken


def test_the_poll_time_is_not_too_small() -> None:
    watcher = HotkeyWatcher(lambda: None, poll_seconds=0.0)
    assert watcher.poll_seconds >= 0.02


def test_the_watcher_stops_within_a_while() -> None:
    watcher = HotkeyWatcher(lambda: None)
    watcher.start()
    time.sleep(0.1)
    watcher.stop(timeout=3.0)
    assert watcher.is_running is False
