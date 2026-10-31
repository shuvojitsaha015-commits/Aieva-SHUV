"""Phase 12: the global error handler (no exception may reach the teacher)."""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module", autouse=True)
def _window():
    from kivy.core.window import Window  # noqa: F401

    return Window


def test_the_message_is_shortened():
    from aieva.ui.error_handler import MAX_TOAST, short_message

    assert short_message(ValueError("a")) == "a"
    assert short_message(ValueError("x" * 500)).endswith("...")
    assert len(short_message(ValueError("x" * 500))) <= MAX_TOAST
    assert short_message(ValueError("")) == "ValueError"


def test_the_traceback_is_written_to_the_log(tmp_path, monkeypatch):
    from aieva.ui import error_handler

    log = tmp_path / "aieva.log"
    monkeypatch.setattr(error_handler, "log_file_path", lambda: log)
    try:
        raise ValueError("something went wrong")
    except ValueError as exc:
        path = error_handler.report_exception(exc, "the test")
    assert path == log
    assert log.is_file()
    content = log.read_text(encoding="utf-8")
    assert "something went wrong" in content
    assert "the test" in content


def test_the_handler_is_installed(tmp_path, monkeypatch):
    from aieva.ui import error_handler

    monkeypatch.setattr(error_handler, "log_file_path", lambda: tmp_path / "aieva.log")
    previous = sys.excepthook
    try:
        error_handler.install_global_handler()
        assert sys.excepthook is not previous
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        assert (tmp_path / "aieva.log").is_file()
    finally:
        sys.excepthook = previous


def test_the_handler_calls_the_callback(tmp_path, monkeypatch):
    from aieva.ui import error_handler

    monkeypatch.setattr(error_handler, "log_file_path", lambda: tmp_path / "aieva.log")
    seen: list[BaseException] = []
    previous = sys.excepthook
    try:
        error_handler.install_global_handler(seen.append)
        try:
            raise ValueError("with a callback")
        except ValueError:
            sys.excepthook(*sys.exc_info())
        assert seen and isinstance(seen[0], ValueError)
    finally:
        sys.excepthook = previous


def test_the_keyboard_interrupt_is_not_swallowed(tmp_path, monkeypatch):
    from aieva.ui import error_handler

    monkeypatch.setattr(error_handler, "log_file_path", lambda: tmp_path / "aieva.log")
    previous = sys.excepthook
    raised: list[bool] = []

    def _original(*args):
        raised.append(True)

    monkeypatch.setattr(sys, "__excepthook__", _original)
    try:
        error_handler.install_global_handler()
        sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        assert raised
    finally:
        sys.excepthook = previous


def test_the_app_installs_the_handler():
    """The application itself installs the handler when it starts."""
    from pathlib import Path

    source = Path(__import__("aieva.ui.app", fromlist=["x"]).__file__).read_text(encoding="utf-8")
    assert "install_global_handler" in source
