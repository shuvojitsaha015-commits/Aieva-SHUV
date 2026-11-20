"""The command line of the background board service.

python -m aieva.core.service run               # the background application
python -m aieva.core.service once              # one reading (for the tests)
python -m aieva.core.service status            # what the service is doing
python -m aieva.core.service install-autostart  # start with the computer
python -m aieva.core.service uninstall-autostart
python -m aieva.core.service overlay           # the floating window
python -m aieva.core.service tray             # the icon in the system tray
"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from aieva.core.service.autostart import install_autostart, install_with_fallback, remove_autostart
from aieva.core.service.config import SOURCES, ServiceConfig, resolve
from aieva.core.service.hotkey import HotkeyWatcher
from aieva.core.service.runner import BackgroundService, result_path
from aieva.core.service.state import ServiceState

LOGGER = logging.getLogger(__name__)

#: The name of the service in the logs.
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(config: ServiceConfig, verbose: bool = False) -> None:
    """Write the log into the log file and into the console."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        log_path = resolve(config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
        )
    except OSError as exc:  # pragma: no cover - a read only disk
        print(f"The log file could not be opened: {exc}")
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
        force=True,
    )


def config_from_args(args: argparse.Namespace) -> ServiceConfig:
    """The configuration of the command line (over the environment)."""
    config = ServiceConfig.from_env()
    changes: dict[str, Any] = {}
    source = getattr(args, "source", None)
    if source:
        changes["source"] = source
    interval = getattr(args, "interval", None)
    if interval:
        changes["poll_seconds"] = float(interval)
    if getattr(args, "mock", False):
        changes["mock_ocr"] = True
    if getattr(args, "overlay", False):
        changes["overlay"] = True
    if getattr(args, "no_solve", False):
        changes["auto_solve"] = False
    if getattr(args, "no_plot", False):
        changes["auto_plot"] = False
    if getattr(args, "folder", None):
        changes["folder"] = Path(args.folder)
    if getattr(args, "outbox", None):
        changes["outbox"] = Path(args.outbox)
    if getattr(args, "state_file", None):
        changes["state_file"] = Path(args.state_file)
    return config.replaced(**changes)


def _install_signals(service: BackgroundService) -> None:
    """Stop the service when the computer shuts down."""

    def handler(_signum: int, _frame: Any) -> None:
        LOGGER.info("The service is asked to stop")
        service.stop()

    for name in ("SIGINT", "SIGTERM"):
        number = getattr(signal, name, None)
        if number is None:
            continue
        try:
            signal.signal(number, handler)
        except (ValueError, OSError):  # pragma: no cover - not the main thread
            pass


def _start_overlay(config: ServiceConfig) -> None:
    """Start the floating window in its own process."""
    command = [
        sys.executable,
        "-m",
        "aieva.ui.board_overlay",
        "--state-file",
        str(config.state_file),
    ]
    env = dict(os.environ)
    env["KIVY_NO_ARGS"] = "1"
    try:
        subprocess.Popen(
            command,
            cwd=str(Path.cwd()),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        LOGGER.info("The floating window was started")
    except OSError as exc:  # pragma: no cover - depends on the system
        LOGGER.warning("The floating window could not be started: %s", exc)


def _start_tray(config: ServiceConfig) -> None:
    """Show the icon of Aieva in the system tray of Windows."""
    command = [
        sys.executable,
        "-m",
        "aieva.core.service",
        "tray",
        "--state-file",
        str(config.state_file),
    ]
    try:
        subprocess.Popen(
            command,
            cwd=str(Path.cwd()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        LOGGER.info("The icon of Aieva is in the system tray")
    except OSError as exc:  # pragma: no cover - depends on the system
        LOGGER.warning("The icon of Aieva could not be shown: %s", exc)


def _tray(config: ServiceConfig, args: argparse.Namespace) -> int:
    """The icon of Aieva in the system tray."""
    from aieva.core.service.tray import run_tray

    return run_tray(config.state_file)


def _run(config: ServiceConfig, args: argparse.Namespace) -> int:
    """The background application."""
    service = BackgroundService(config=config)
    _install_signals(service)
    _start_overlay(config)
    if getattr(args, "tray", False):
        _start_tray(config)
    watcher: HotkeyWatcher | None = None
    keys = tuple(getattr(args, "hotkey", ()) or ()) or tuple(config.hotkey)
    if keys:
        watcher = HotkeyWatcher(lambda: _scan_on_request(service), keys=keys)
        watcher.start()
        print(f"The key {', '.join(keys)} reads the board.")
    print("Aieva watches the board - press Ctrl+C to stop it.")
    try:
        service.run_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive
        pass
    finally:
        if watcher is not None:
            watcher.stop()
        service.stop()
    return 0


def _scan_on_request(service: BackgroundService) -> None:
    """The key was pressed - read the board."""
    try:
        service.scan_now()
    except Exception as exc:  # noqa: BLE001 - the service must survive
        LOGGER.warning("The board could not be read: %s", exc)


def _scan(config: ServiceConfig, args: argparse.Namespace) -> int:
    """Read the board once - right now, on purpose."""
    service = BackgroundService(config=config)
    try:
        run = service.scan_now()
    except Exception as exc:  # noqa: BLE001 - the teacher sees the reason
        print(f"The board could not be read: {exc}", file=sys.stderr)
        return 1
    if not run.plain and not run.latex:
        print(run.error or "Nothing was found on the board.")
        return 1
    print(run.plain or run.latex)
    if run.answer:
        print(run.answer)
    return 0


def _doctor(config: ServiceConfig, args: argparse.Namespace) -> int:
    """Is this computer ready for the board?"""
    from aieva.core.doctor import build_report

    report = build_report()
    print(report.render())
    return 0 if report.ready else 1


def _once(config: ServiceConfig, args: argparse.Namespace) -> int:
    """One reading."""
    service = BackgroundService(config=config)
    run = service.run_once()
    print(json.dumps(run.to_dict(), indent=2, ensure_ascii=False))
    return 0 if run.ran or not run.error else 1


def _status(config: ServiceConfig, args: argparse.Namespace) -> int:
    """What the service is doing."""
    state = ServiceState.load(config.state_file)
    print(f"service : {state.service} {state.version}")
    print(f"status  : {state.status}")
    print(f"pid     : {state.pid}")
    print(f"uptime  : {state.uptime_seconds():.0f} s")
    print(f"readings: {state.runs} (errors: {state.errors})")
    if state.last_plain or state.last_latex:
        print(f"last    : {state.last_plain or state.last_latex}")
    if state.last_answer:
        print(f"answer  : {state.last_answer}")
    if state.last_error:
        print(f"error   : {state.last_error}")
    print(f"file    : {resolve(config.state_file)}")
    print(f"results : {result_path(config.state_file)}")
    return 0


def _install_autostart(config: ServiceConfig, args: argparse.Namespace) -> int:
    """Start the service automatically with the computer.

    Without a trigger the best way the computer allows is used: the boot
    first (it needs administrator rights), then the login.
    """
    trigger = getattr(args, "trigger", "")
    with_window = bool(getattr(args, "with_window", False))
    if trigger:
        message = install_autostart(
            project_dir=Path.cwd(), trigger=trigger, with_window=with_window
        )
    else:
        message = install_with_fallback(project_dir=Path.cwd(), with_window=with_window)
    print(message)
    print(
        "The board service now starts with the computer. "
        "Check it with: python -m aieva.core.doctor"
    )
    return 0


def _uninstall_autostart(config: ServiceConfig, args: argparse.Namespace) -> int:
    """Undo the automatic start."""
    print(remove_autostart())
    return 0


def _overlay(config: ServiceConfig, args: argparse.Namespace) -> int:
    """The floating window."""
    from aieva.ui import board_overlay

    return board_overlay.main(
        [
            "--state-file",
            str(config.state_file),
            "--seconds",
            str(config.overlay_seconds),
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    """The command line of the service."""
    parser = argparse.ArgumentParser(
        prog="aieva-service",
        description="Aieva - the background service of the smart board.",
    )
    sub = parser.add_subparsers(dest="command")

    def add_common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--source", choices=list(SOURCES), help="what is watched")
        target.add_argument("--interval", type=float, help="how often the board is looked at")
        target.add_argument("--mock", action="store_true", help="use the mock OCR")
        target.add_argument("--overlay", action="store_true", help="show the floating window")
        target.add_argument(
            "--tray", action="store_true", help="show the icon of Aieva in the system tray"
        )
        target.add_argument("--no-solve", action="store_true", help="do not solve the reading")
        target.add_argument("--no-plot", action="store_true", help="do not draw the reading")
        target.add_argument("--folder", help="the folder with the pictures of the board")
        target.add_argument("--outbox", help="where the results are written")
        target.add_argument("--state-file", help="the status file of the service")
        target.add_argument(
            "--hotkey",
            action="append",
            help="a key that reads the board (f8, f9, ... - it can be given twice)",
        )
        target.add_argument("--verbose", action="store_true", help="log every step")

    run = sub.add_parser("run", help="watch the board in the background")
    add_common(run)

    once = sub.add_parser("once", help="read the board once and stop")
    add_common(once)

    status = sub.add_parser("status", help="show what the service is doing")
    add_common(status)

    install = sub.add_parser("install-autostart", help="start the service with the computer")
    install.add_argument(
        "--with-window",
        action="store_true",
        help="start the window of the teacher too",
    )
    install.add_argument(
        "--trigger",
        choices=("onlogon", "onstart"),
        default="",
        help=(
            "when the service starts (onlogon needs no rights, onstart does). "
            "Without it the boot is tried first and the login is the fallback."
        ),
    )

    sub.add_parser("uninstall-autostart", help="stop starting the service")

    sub.add_parser("doctor", help="is this computer ready to read the board?")

    scan = sub.add_parser("scan", help="read the board once, right now")
    scan.add_argument("--state-file", help="the status file of the service")

    overlay = sub.add_parser("overlay", help="the floating window above the board")
    overlay.add_argument("--seconds", type=float, default=8.0, help="how long it stays")
    overlay.add_argument("--verbose", action="store_true", help="log every step")

    tray = sub.add_parser("tray", help="the icon of Aieva in the system tray")
    tray.add_argument("--state-file", help="the status file of the service")

    return parser


def main(argv: list[str] | None = None) -> int:
    """The entry point of the background service."""
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "run"
    config = config_from_args(args)
    setup_logging(config, verbose=bool(getattr(args, "verbose", False)))
    handlers = {
        "run": _run,
        "once": _once,
        "status": _status,
        "install-autostart": _install_autostart,
        "uninstall-autostart": _uninstall_autostart,
        "overlay": _overlay,
        "tray": _tray,
        "doctor": _doctor,
        "scan": _scan,
    }
    handler = handlers.get(command)
    if handler is None:  # pragma: no cover - argparse rejects unknown commands
        parser.print_help()
        return 2
    return handler(config, args)


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())


__all__ = ["build_parser", "config_from_args", "main", "setup_logging"]
