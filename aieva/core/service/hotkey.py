"""A key that asks for a reading of the board.

On a smart board the teacher often has a keyboard (or a remote) at hand.
``F8`` (or ``Ctrl+Alt+A``) reads the board without touching the screen.

Every platform gets the key it can deliver:

* **Windows** - the key is registered with the system (``RegisterHotKey``);
  if that fails it is polled. This is the platform of Aieva.
* **The button** of the floating window does the same thing - it works
  everywhere.

The callback always runs in a background thread - the user interface is
never blocked.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The keys that can be used (the name is the one of the ``KeyEvent``).
DEFAULT_KEYS: tuple[str, ...] = ("f8",)

#: The virtual key codes of Windows.
_VIRTUAL_KEYS: dict[str, int] = {
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}


class HotkeyWatcher:
    """Waits for a key and calls the callback when it is pressed."""

    def __init__(
        self,
        callback: Callable[[], Any],
        keys: tuple[str, ...] = DEFAULT_KEYS,
        poll_seconds: float = 0.05,
    ) -> None:
        self.callback = callback
        self.keys = tuple(key.lower() for key in keys) or DEFAULT_KEYS
        self.poll_seconds = max(0.02, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._registered = False

    # ------------------------------------------------------------------ api
    def start(self) -> None:
        """Start watching (in a background thread)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="aieva-hotkey", daemon=True)
        self._thread.start()
        LOGGER.info("The key %s reads the board", ", ".join(self.keys))

    def stop(self, timeout: float = 2.0) -> None:
        """Stop watching."""
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        """Is the watcher running?"""
        thread = self._thread
        return thread is not None and thread.is_alive()

    # ------------------------------------------------------------ internals
    def _loop(self) -> None:
        """Watch the key - with the way this system can do it."""
        if sys.platform.startswith("win"):
            try:
                self._loop_windows()
                return
            except Exception as exc:  # noqa: BLE001 - fall back to the polling
                LOGGER.info("The key could not be registered (%s) - it is polled now", exc)
            self._loop_polling_windows()
            return
        self._loop_pynput()

    def _loop_windows(self) -> None:
        """Wait for the key with the help of Windows."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hotkey_id = 0xA1E7
        modifiers = 0x0003  # ALT + CONTROL
        registered: list[int] = []
        for index, key in enumerate(self.keys):
            code = _VIRTUAL_KEYS.get(key)
            if code is None:
                continue
            if user32.RegisterHotKey(None, hotkey_id + index, modifiers, code):
                registered.append(hotkey_id + index)
        if not registered:
            raise RuntimeError("no key could be registered")
        self._registered = True
        try:
            message = wintypes.MSG()
            while not self._stop.is_set():
                result = user32.GetMessageW(ctypes.byref(message), 0, 0, 0)
                if result in (0, -1):
                    break
                if message.message == 0x0312:  # WM_HOTKEY
                    self._fire()
        finally:
            for identifier in registered:
                user32.UnregisterHotKey(None, identifier)
            self._registered = False

    def _loop_polling_windows(self) -> None:
        """Wait for the key by asking Windows for its state."""
        import ctypes

        user32 = ctypes.windll.user32
        pressed: set[str] = set()
        while not self._stop.is_set():
            for key in self.keys:
                code = _VIRTUAL_KEYS.get(key)
                if code is None:
                    continue
                down = bool(user32.GetAsyncKeyState(code) & 0x8000)
                if down and key not in pressed:
                    pressed.add(key)
                    self._fire()
                elif not down:
                    pressed.discard(key)
            time.sleep(self.poll_seconds)

    def _loop_pynput(self) -> None:
        """Wait for the key with ``pynput`` (the development machines)."""
        try:
            from pynput import keyboard
        except Exception:  # noqa: BLE001 - the package is optional
            LOGGER.info(
                "The key is not watched on this system - install pynput "
                "or use the button of the window"
            )
            while not self._stop.is_set():
                time.sleep(self.poll_seconds)
            return

        wanted = {f"<{key}>" for key in self.keys}
        pressed: set[str] = set()

        def on_press(key: Any) -> None:
            name = getattr(key, "name", "")
            if name and name.lower() in self.keys and name.lower() not in pressed:
                pressed.add(name.lower())
                self._fire()

        def on_release(key: Any) -> None:
            name = getattr(key, "name", "")
            if name:
                pressed.discard(name.lower())

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()
        try:
            while not self._stop.is_set() and listener.is_alive():
                time.sleep(self.poll_seconds)
        finally:
            listener.stop()
        _ = wanted

    def _fire(self) -> None:
        """Tell the listener about the key."""
        try:
            self.callback()
        except Exception:  # noqa: BLE001 - a broken listener must not kill the watcher
            LOGGER.exception("The key could not be handled")


__all__ = ["DEFAULT_KEYS", "HotkeyWatcher"]
