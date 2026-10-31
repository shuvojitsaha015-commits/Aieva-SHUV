"""The global error handler of the application.

No unhandled exception may reach the teacher. The handler

* writes the traceback into ``aieva.log`` (the file of the settings), so
  that a bug can be found later, and
* shows a short **toast** with what went wrong.

The handler is installed for the Python exceptions (``sys.excepthook``) and
for the exceptions of the Kivy event loop.
"""

from __future__ import annotations

import logging
import sys
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("aieva.error")

#: The maximum length of the message that is shown to the user.
MAX_TOAST = 160


def log_file_path() -> Path:
    """The file the errors are written to (``aieva.log`` by default)."""
    from aieva.config import get_settings

    path = Path(get_settings().log_file)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def report_exception(exc: BaseException, context: str = "") -> Path:
    """Write the traceback into the log file and return the file."""
    path = log_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"--- {datetime.now().isoformat(timespec='seconds')} {context}\n")
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)
            handle.write("\n")
    except OSError as error:  # pragma: no cover - a broken disk
        LOGGER.warning("The error could not be written to %s: %s", path, error)
    return path


def short_message(exc: BaseException) -> str:
    """A short message for the toast."""
    text = str(exc).strip() or exc.__class__.__name__
    if len(text) > MAX_TOAST:
        text = text[: MAX_TOAST - 3] + "..."
    return text


def install_global_handler(on_error: Callable[[BaseException], None] | None = None) -> None:
    """Install the handler for the exceptions of Python and of Kivy."""

    def hook(exc_type: Any, exc_value: Any, exc_tb: Any) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        if isinstance(exc_value, BaseException):
            report_exception(exc_value, "unhandled exception")
            LOGGER.exception("An unhandled exception reached the user", exc_info=exc_value)
            if on_error is not None:
                try:
                    on_error(exc_value)
                    return
                except Exception:  # noqa: BLE001 - the handler must not fail
                    pass
            _toast(f"Something went wrong: {short_message(exc_value)}")

    sys.excepthook = hook

    try:
        from kivy.base import ExceptionManager

        ExceptionManager.add_exception_handler("aieva", hook)
    except Exception as exc:  # noqa: BLE001 - Kivy is optional here
        LOGGER.info("The Kivy exception handler could not be installed: %s", exc)


def _toast(message: str) -> None:
    """Show the toast (the UI is optional)."""
    try:
        from aieva.ui.widgets.toast import show_toast

        show_toast(message)
    except Exception as exc:  # noqa: BLE001 - never fail because of the toast
        LOGGER.info("The toast could not be shown: %s", exc)


__all__ = [
    "MAX_TOAST",
    "install_global_handler",
    "log_file_path",
    "report_exception",
    "short_message",
]
