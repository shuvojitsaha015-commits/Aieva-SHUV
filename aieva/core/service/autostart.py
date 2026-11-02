"""Starting the service automatically with the board.

A smart board is switched on in the morning and the teacher should not have
to do anything - the service has to be there already. The platform decides
how:

* **Windows** - a task of the Task Scheduler. ``ONLOGON`` starts the service
  when somebody logs in (no administrator rights needed), ``ONSTART`` when the
  computer starts (administrator rights needed). The task calls a small
  batch file that starts the service with ``pythonw.exe``, so no console
  window ever appears on the board.
* **Linux / Termux (an Android board)** - a systemd unit.
* **macOS** - a launch agent.

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

#: The unit name of the systemd service.
UNIT_NAME = "aieva.service"

#: The triggers the task scheduler understands.
TRIGGERS: dict[str, str] = {
    "onlogon": "ONLOGON",
    "onstart": "ONSTART",
    "ondaily": "ONDAILY",
}

#: The signature of the function that runs a command.
Runner = Callable[..., Any]


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


def launcher_text(python_exe: str, project_dir: str, extra_args: str = "") -> str:
    """The batch file that starts the service in the background."""
    arguments = f" -m aieva.core.service run {extra_args}".rstrip()
    return (
        "@echo off\r\n"
        "rem Aieva - the background service of the smart board\r\n"
        f'cd /d "{project_dir}"\r\n'
        f'start "" "{python_exe}"{arguments}\r\n'
    )


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
) -> str:
    """Register the service with the task scheduler of Windows."""
    runner = runner or subprocess.run
    executable = pythonw_path(python_exe or sys.executable)
    project = str(Path(project_dir) if project_dir else Path.cwd())
    launcher = launcher_path()
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(launcher_text(executable, project, extra_args), encoding="utf-8")
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


def systemd_unit_text(
    project_dir: str | Path, python_exe: str | Path | None = None, extra_args: str = ""
) -> str:
    """The systemd unit that starts the service."""
    executable = str(python_exe or sys.executable)
    arguments = f"-m aieva.core.service run {extra_args}".rstrip()
    return (
        "[Unit]\n"
        "Description=Aieva - the background service of the smart board\n"
        "After=graphical-session.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={project_dir}\n"
        f"ExecStart={executable} {arguments}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def install_systemd(
    project_dir: str | Path | None = None,
    python_exe: str | Path | None = None,
    unit_name: str = UNIT_NAME,
    extra_args: str = "",
) -> str:
    """Write the systemd unit of the service (the user has to enable it)."""
    project = str(Path(project_dir) if project_dir else Path.cwd())
    directory = Path.home() / ".config" / "systemd" / "user"
    directory.mkdir(parents=True, exist_ok=True)
    unit = directory / unit_name
    unit.write_text(systemd_unit_text(project, python_exe, extra_args), encoding="utf-8")
    return (
        f"The unit was written to {unit}.\n"
        "Enable it with:\n"
        f"   systemctl --user daemon-reload\n"
        f"   systemctl --user enable --now {unit_name}\n"
    )


def launch_agent_text(
    project_dir: str | Path, python_exe: str | Path | None = None, extra_args: str = ""
) -> str:
    """The launch agent of macOS."""
    executable = str(python_exe or sys.executable)
    arguments = f"-m aieva.core.service run {extra_args}".rstrip()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "    <key>Label</key>\n"
        "    <string>com.aieva.board-service</string>\n"
        "    <key>ProgramArguments</key>\n"
        "    <array>\n"
        f"        <string>{executable}</string>\n"
        f"        <string>{arguments}</string>\n"
        "    </array>\n"
        "    <key>WorkingDirectory</key>\n"
        f"    <string>{project_dir}</string>\n"
        "    <key>RunAtLoad</key>\n"
        "    <true/>\n"
        "    <key>KeepAlive</key>\n"
        "    <true/>\n"
        "</dict>\n"
        "</plist>\n"
    )


def install_launch_agent(
    project_dir: str | Path | None = None, python_exe: str | Path | None = None
) -> str:
    """Write the launch agent of macOS."""
    project = str(Path(project_dir) if project_dir else Path.cwd())
    directory = Path.home() / "Library" / "LaunchAgents"
    directory.mkdir(parents=True, exist_ok=True)
    agent = directory / "com.aieva.board-service.plist"
    agent.write_text(launch_agent_text(project, python_exe), encoding="utf-8")
    return f"The launch agent was written to {agent}.\nLoad it with:\n   launchctl load {agent}\n"


def install_autostart(
    project_dir: str | Path | None = None,
    python_exe: str | Path | None = None,
    trigger: str = "onlogon",
    runner: Runner | None = None,
) -> str:
    """Start the service automatically with the operating system."""
    if sys.platform.startswith("win"):
        return install_windows_task(
            python_exe=python_exe, project_dir=project_dir, trigger=trigger, runner=runner
        )
    if sys.platform == "darwin":
        return install_launch_agent(project_dir=project_dir, python_exe=python_exe)
    return install_systemd(project_dir=project_dir, python_exe=python_exe)


def remove_autostart(runner: Runner | None = None) -> str:
    """Undo :func:`install_autostart`."""
    if sys.platform.startswith("win"):
        return remove_windows_task(runner=runner)
    if sys.platform == "darwin":
        agent = Path.home() / "LaunchAgents" / "com.aieva.board-service.plist"
        if agent.is_file():
            agent.unlink()
        return f"The launch agent {agent} was removed."
    unit = Path.home() / ".config" / "systemd" / "user" / UNIT_NAME
    if unit.is_file():
        unit.unlink()
    return f"The unit {unit} was removed."


__all__ = [
    "TASK_NAME",
    "UNIT_NAME",
    "TRIGGERS",
    "install_autostart",
    "install_launch_agent",
    "install_systemd",
    "install_windows_task",
    "launch_agent_text",
    "launcher_path",
    "launcher_text",
    "local_data_dir",
    "pythonw_path",
    "remove_autostart",
    "remove_windows_task",
    "systemd_unit_text",
    "windows_task_arguments",
]
