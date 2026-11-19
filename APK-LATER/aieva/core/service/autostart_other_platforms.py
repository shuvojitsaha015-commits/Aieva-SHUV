"""The automatic start on Linux, Termux and macOS - PARKED, not used.

Aieva is a Windows application. This file keeps the code that started the
service on the other platforms; nothing in ``aieva/`` imports it.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

LOGGER = logging.getLogger(__name__)

#: The unit name of the systemd service.
UNIT_NAME = "aieva.service"


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
    project_dir: str | Path | None = None,
    python_exe: str | Path | None = None,
    extra_args: str = "",
) -> str:
    """Write the launch agent of macOS."""
    project = str(Path(project_dir) if project_dir else Path.cwd())
    directory = Path.home() / "Library" / "LaunchAgents"
    directory.mkdir(parents=True, exist_ok=True)
    agent = directory / "com.aieva.board-service.plist"
    agent.write_text(launch_agent_text(project, python_exe), encoding="utf-8")
    return f"The launch agent was written to {agent}.\nLoad it with:\n   launchctl load {agent}\n"



__all__ = [
    "install_launch_agent",
    "install_systemd",
    "systemd_unit_text",
]
