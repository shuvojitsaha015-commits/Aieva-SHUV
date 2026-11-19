"""The icon of Aieva in the system tray of Windows.

Aieva runs in the background of the board. The teacher needs a way to get
back to it - and a way to read the board - without opening a console window.

The **tray icon** is that way:

* *Open Aieva* starts the full application (``python -m aieva.ui.app``) as a
  child process. The application is a *separate* window - the teacher opens
  it only when they want it.
* *Scan the board* asks the background service to read the board right now
  (the same request file the floating window uses).
* *Stop the service* / *Start the service* pauses and resumes the watching.
* *Quit* stops everything.

``pystray`` is **optional**: it is imported inside the functions that need
it, so the core of Aieva still works on a machine without it (and the tests
run everywhere). When it is missing the module still answers the questions
the tests ask - it just cannot draw an icon.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The name of the tray icon (shown in the tooltip).
TRAY_NAME = "Aieva"

#: The tooltip of the icon.
TRAY_TITLE = "Aieva - the smart board"

#: The text of the menu entries.
MENU_OPEN = "Open Aieva"
MENU_SCAN = "Scan the board"
MENU_START = "Start the service"
MENU_STOP = "Stop the service"
MENU_QUIT = "Quit"

#: The size of the icon in pixels.
ICON_SIZE = 64


@dataclass
class TrayCommand:
    """One entry of the tray menu.

    The command is built without ``pystray`` - the menu is turned into real
    ``pystray`` items only at the very end. That keeps the logic testable on
    every machine.
    """

    #: The text the teacher sees.
    label: str
    #: What the entry does.
    action: str
    #: ``True`` when the entry cannot be used right now.
    disabled: bool = False


def menu_commands(service_running: bool = True) -> list[TrayCommand]:
    """The entries of the menu, in the order they are shown."""
    return [
        TrayCommand(MENU_OPEN, "open"),
        TrayCommand(MENU_SCAN, "scan"),
        TrayCommand(MENU_START if not service_running else MENU_STOP, "toggle"),
        TrayCommand(MENU_QUIT, "quit"),
    ]


def make_icon(size: int = ICON_SIZE) -> Any:
    """Draw the icon of Aieva (a blue square with a white "A").

    The icon is drawn with Pillow - no image file has to be shipped.
    """
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = max(1, size // 12)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=max(2, size // 6),
        fill=(10, 38, 230, 255),
    )
    try:
        font = ImageFont.load_default(size=int(size * 0.62))
    except TypeError:  # pragma: no cover - very old Pillow
        font = ImageFont.load_default()
    text = "A"
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    height = box[3] - box[1]
    draw.text(
        ((size - width) / 2 - box[0], (size - height) / 2 - box[1]),
        text,
        font=font,
        fill=(240, 241, 245, 255),
    )
    return image


def tray_available() -> bool:
    """Can the tray icon be drawn on this machine?"""
    try:
        import pystray  # noqa: F401
    except Exception:  # noqa: BLE001 - the import fails without a display
        return False
    return True


def open_frontend(python_exe: str | Path | None = None) -> str:
    """Start the full application of the teacher.

    It is a **separate process**: the board keeps watching while the teacher
    works in the application.
    """
    executable = str(python_exe or sys.executable)
    command = [executable, "-m", "aieva.ui.app"]
    try:
        subprocess.Popen(  # noqa: S603 - the command is built here, not by the user
            command,
            cwd=str(Path.cwd()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:  # pragma: no cover - depends on the machine
        return f"The application could not be started: {exc}"
    return "The application is starting."


def scan_board(state_file: str | Path) -> str:
    """Ask the background service to read the board right now."""
    from aieva.core.service.scan import write_request

    try:
        write_request(state_file)
    except OSError as exc:  # pragma: no cover - a read only disk
        return f"The board could not be asked for: {exc}"
    return "The board is read."


def stop_service(state_file: str | Path) -> str:
    """Ask the background service to stop.

    The service writes a small stop file - the same way the request file
    works. That way the tray does not have to know the process id.
    """
    from aieva.core.service.state import write_stop_request

    try:
        write_stop_request(state_file)
    except OSError as exc:  # pragma: no cover - a read only disk
        return f"The service could not be stopped: {exc}"
    return "The service stops."


def start_service(state_file: str | Path) -> str:
    """Start the background service again."""
    from aieva.core.service.config import ServiceConfig
    from aieva.core.service.runner import BackgroundService

    config = ServiceConfig.from_env().replaced(state_file=Path(state_file))
    service = BackgroundService(config=config)
    service.start()
    return "The service watches the board."


def dispatch(
    action: str,
    state_file: str | Path,
    service_running: bool = True,
    opener: Callable[[str | Path | None], str] = open_frontend,
    scanner: Callable[[str | Path], str] = scan_board,
    stopper: Callable[[str | Path], str] = stop_service,
    starter: Callable[[str | Path], str] = start_service,
    exiter: Callable[[int], None] = os._exit,
) -> str:
    """Do what the menu entry says.

    Every side effect is a parameter, so the tests can watch what happens
    without starting anything.
    """
    if action == "open":
        return opener(None)
    if action == "scan":
        return scanner(state_file)
    if action == "toggle":
        return stopper(state_file) if service_running else starter(state_file)
    if action == "quit":
        message = stopper(state_file)
        exiter(0)
        return message
    return "Nothing to do."


def build_menu(
    state_file: str | Path,
    service_running: bool = True,
    actions: Callable[[str], str] | None = None,
) -> Any:
    """The real ``pystray`` menu.

    ``pystray`` is imported here (and not at the top of the file), so the
    module can be imported on a machine without it.
    """
    import pystray

    run = actions or (lambda action: dispatch(action, state_file, service_running))

    def handle(command: TrayCommand) -> Any:
        def inner(_icon: Any = None, _item: Any = None) -> str:
            return run(command.action)

        return inner

    items = [
        pystray.MenuItem(
            command.label,
            handle(command),
            enabled=not command.disabled,
        )
        for command in menu_commands(service_running)
    ]
    items.append(pystray.Menu.SEPARATOR)
    items.append(pystray.MenuItem(MENU_QUIT, handle(TrayCommand(MENU_QUIT, "quit"))))
    return pystray.Menu(*items)


def run_tray(state_file: str | Path, service_running: bool = True) -> int:
    """Show the icon and stay until the teacher quits."""
    if not tray_available():
        print("The system tray is not available on this machine.")
        return 1
    import pystray

    icon = pystray.Icon(
        TRAY_NAME,
        icon=make_icon(),
        title=TRAY_TITLE,
        menu=build_menu(state_file, service_running),
    )
    icon.run()
    return 0


__all__ = [
    "ICON_SIZE",
    "MENU_OPEN",
    "MENU_QUIT",
    "MENU_SCAN",
    "MENU_START",
    "MENU_STOP",
    "TRAY_NAME",
    "TRAY_TITLE",
    "TrayCommand",
    "build_menu",
    "dispatch",
    "make_icon",
    "menu_commands",
    "open_frontend",
    "run_tray",
    "scan_board",
    "start_service",
    "stop_service",
    "tray_available",
]
