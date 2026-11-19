"""Starting the service automatically with the board.

A smart board is switched on in the morning and the teacher should not have
to do anything - the service has to be there already. The platform decides
how:

* **Windows** - a task of the Task Scheduler. ``ONLOGON`` starts the service
  when somebody logs in (no administrator rights needed), ``ONSTART`` when the
  computer starts (administrator rights needed). The task calls a small
  batch file that starts the service with ``pythonw.exe``, so no console
  window ever appears on the board.
* **Windows without administrator rights** - a file in the startup folder of
  the user (it starts the service when the user logs in).

The ``*_text`` / ``*_arguments`` functions only build the text, so they can be
tested on any machine. The ``install_*`` functions write the files and call
the operating system.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The name of the task (Windows) and of the unit (Linux).
TASK_NAME = "Aieva Background Service"

#: The triggers the task scheduler understands.
TRIGGERS: dict[str, str] = {
    "onlogon": "ONLOGON",
    "onstart": "ONSTART",
    "ondaily": "ONDAILY",
}

#: The signature of the function that runs a command.
Runner = Callable[..., Any]


def startup_folder_path() -> Path:
    """The startup folder of the user.

    A file in this folder is started by Windows **every time the computer is
    switched on** - it needs no administrator rights. It is the fallback when
    the task scheduler may not be used.
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home() / ".aieva" / "autostart"


def startup_script_text(python_exe: str, project_dir: str, extra_args: str = "") -> str:
    """The file that the startup folder runs."""
    arguments = f" -m aieva.core.service run {extra_args}".rstrip()
    return (
        "@echo off\r\n"
        "rem Aieva - it starts with the computer\r\n"
        f'cd /d "{project_dir}"\r\n'
        f'start "" "{python_exe}"{arguments}\r\n'
    )


def install_startup_folder(
    python_exe: str | Path | None = None,
    project_dir: str | Path | None = None,
    extra_args: str = "--overlay",
) -> str:
    """Let Windows start Aieva with the computer (no rights needed)."""
    executable = pythonw_path(python_exe or sys.executable)
    project = str(Path(project_dir) if project_dir else Path.cwd())
    folder = startup_folder_path()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "Aieva.cmd"
        target.write_text(startup_script_text(executable, project, extra_args), encoding="utf-8")
    except OSError as exc:
        return f"The startup file could not be written: {exc}"
    return (
        f"The startup file was written to {target}.\n"
        "Aieva now starts with the computer (when the user logs in)."
    )


def remove_startup_folder() -> str:
    """Undo :func:`install_startup_folder`."""
    target = startup_folder_path() / "Aieva.cmd"
    if target.is_file():
        try:
            target.unlink()
        except OSError as exc:
            return f"The startup file could not be removed: {exc}"
    return f"The startup file {target} was removed."


def local_data_dir() -> Path:
    """The folder where the launcher of the service is stored."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "Aieva"
    return Path.home() / ".aieva"


def launcher_path() -> Path:
    """The batch file that starts the service."""
    return local_data_dir() / "run_service.cmd"


def pythonw_path(python_exe: str | Path | None = None) -> str:
    """``pythonw.exe`` when it exists - it starts without a console window."""
    exe = Path(python_exe or sys.executable)
    candidate = exe.with_name("pythonw.exe")
    if candidate.exists():
        return str(candidate)
    return str(exe)


def launcher_text(
    python_exe: str,
    project_dir: str,
    extra_args: str = "",
    with_window: bool = False,
    with_tray: bool = True,
) -> str:
    """The batch file that starts the service in the background.

    The icon of Aieva is shown in the system tray by default - that is how
    the teacher gets back to the application. With ``with_window`` the full
    application is started too, so the board shows it right after the
    computer has been switched on.
    """
    arguments = f" -m aieva.core.service run {extra_args}".rstrip()
    lines = [
        "@echo off\r\n",
        "rem Aieva - the background service of the smart board\r\n",
        f'cd /d "{project_dir}"\r\n',
    ]
    if with_tray and "--tray" not in arguments:
        arguments = f"{arguments} --tray"
    lines.append(f'start "" "{python_exe}"{arguments}\r\n')
    if with_window:
        lines.append(f'start "" "{python_exe}" -m aieva.ui.app\r\n')
    return "".join(lines)


def windows_task_arguments(
    name: str = TASK_NAME, launcher: str | Path = "", trigger: str = "onlogon"
) -> list[str]:
    """The ``schtasks`` command that registers the service."""
    schedule = TRIGGERS.get((trigger or "onlogon").strip().lower(), "ONLOGON")
    return [
        "schtasks",
        "/Create",
        "/SC",
        schedule,
        "/TN",
        name,
        "/TR",
        str(launcher),
        "/F",
    ]


def _describe(
    command: list[str],
    result: Any,
    ok_text: str = "The task was created.",
    fail_text: str = "The task could not be created.",
) -> str:
    """A readable answer for the teacher."""
    code = int(getattr(result, "returncode", 0) or 0)
    output = (getattr(result, "stdout", "") or "").strip()
    errors = (getattr(result, "stderr", "") or "").strip()
    head = ok_text if code == 0 else fail_text
    lines = [head, f"command: {' '.join(command)}"]
    if output:
        lines.append(output)
    if errors:
        lines.append(errors)
    return "\n".join(lines)


def install_windows_task(
    python_exe: str | Path | None = None,
    project_dir: str | Path | None = None,
    trigger: str = "onlogon",
    name: str = TASK_NAME,
    extra_args: str = "",
    runner: Runner | None = None,
    with_window: bool = False,
    with_tray: bool = True,
) -> str:
    """Register the service with the task scheduler of Windows."""
    runner = runner or subprocess.run
    executable = pythonw_path(python_exe or sys.executable)
    project = str(Path(project_dir) if project_dir else Path.cwd())
    launcher = launcher_path()
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        launcher_text(executable, project, extra_args, with_window, with_tray), encoding="utf-8"
    )
    command = windows_task_arguments(name, launcher, trigger)
    try:
        result = runner(command, capture_output=True, text=True)
    except OSError as exc:
        return f"The task could not be created: {exc}"
    return _describe(command, result)


def remove_windows_task(name: str = TASK_NAME, runner: Runner | None = None) -> str:
    """Remove the task again."""
    runner = runner or subprocess.run
    command = ["schtasks", "/Delete", "/TN", name, "/F"]
    try:
        result = runner(command, capture_output=True, text=True)
    except OSError as exc:
        return f"The task could not be removed: {exc}"
    return _describe(
        command,
        result,
        ok_text="The task was removed.",
        fail_text="The task could not be removed.",
    )


def install_autostart(
    project_dir: str | Path | None = None,
    python_exe: str | Path | None = None,
    trigger: str = "onstart",
    runner: Runner | None = None,
    extra_args: str = "--overlay",
    with_window: bool = False,
    with_tray: bool = True,
) -> str:
    """Start the service automatically with the operating system.

    The floating window (the control of the board) is started with it, so
    the teacher finds the button *Scan* already there after the computer
    has been switched on.

    The trigger is **ONSTART** - the service starts when the computer
    **boots**, not only when somebody logs in. That needs administrator
    rights; when they are missing the task falls back to *ONLOGON* and the
    startup folder of the user is the last way out.
    """
    if sys.platform.startswith("win"):
        return install_windows_task(
            python_exe=python_exe,
            project_dir=project_dir,
            trigger=trigger,
            runner=runner,
            extra_args=extra_args,
            with_window=with_window,
            with_tray=with_tray,
        )
    # Aieva is a Windows application - there is nothing else to do here.
    raise RuntimeError("Aieva starts automatically on Windows only")


def install_with_fallback(
    project_dir: str | Path | None = None,
    python_exe: str | Path | None = None,
    runner: Runner | None = None,
    extra_args: str = "--overlay",
    with_window: bool = False,
    with_tray: bool = True,
) -> str:
    """Install the automatic start the best way the computer allows.

    The order is:

    1. a task of the task scheduler that starts at the **boot**
       (``ONSTART`` - it needs administrator rights),
    2. a task that starts at the **login** (``ONLOGON`` - no rights needed),
    3. a file in the **startup folder** of the user (also at the login).

    The answer says which one was used - the teacher has to know when the
    board needs an administrator to start.
    """
    if not sys.platform.startswith("win"):
        raise RuntimeError("Aieva starts automatically on Windows only")

    first = install_windows_task(
        python_exe=python_exe,
        project_dir=project_dir,
        trigger="onstart",
        runner=runner,
        extra_args=extra_args,
        with_window=with_window,
        with_tray=with_tray,
    )
    if _succeeded(first):
        return "The task was created: Aieva starts when the computer boots.\n" f"{first}"

    second = install_windows_task(
        python_exe=python_exe,
        project_dir=project_dir,
        trigger="onlogon",
        runner=runner,
        extra_args=extra_args,
        with_window=with_window,
        with_tray=with_tray,
    )
    if _succeeded(second):
        return (
            "The task was created: Aieva starts when the teacher logs in "
            "(the boot needs administrator rights).\n"
            f"{second}"
        )

    return install_startup_folder(python_exe=python_exe, project_dir=project_dir)


def _succeeded(message: str) -> bool:
    """Did the command work?"""
    text = (message or "").lower()
    if "could not be created" in text:
        return False
    if "error" in text or "access is denied" in text:
        return False
    return "task was created" in text or "the task was created" in text


def remove_autostart(runner: Runner | None = None) -> str:
    """Undo :func:`install_autostart`."""
    if sys.platform.startswith("win"):
        return remove_windows_task(runner=runner)
    raise RuntimeError("Aieva starts automatically on Windows only")


__all__ = [
    "TASK_NAME",
    "TRIGGERS",
    "install_autostart",
    "install_with_fallback",
    "install_startup_folder",
    "install_windows_task",
    "launcher_path",
    "launcher_text",
    "local_data_dir",
    "pythonw_path",
    "remove_autostart",
    "remove_startup_folder",
    "remove_windows_task",
    "startup_folder_path",
    "startup_script_text",
    "windows_task_arguments",
]
