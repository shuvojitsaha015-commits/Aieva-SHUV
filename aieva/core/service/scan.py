"""Asking the service to read the board right now.

The teacher writes something on the board and **taps** it - like the Google
Lens of a phone. The tap writes a small request file, the background service
sees it, reads the board, solves it and publishes the result. The floating
window shows it.

The request file is the simplest possible communication between the window
and the service: no socket, no port, nothing that can block.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The name of the request file (next to the status file).
REQUEST_FILE_NAME = "scan_request"

#: The name of the file with the area the teacher picked last.
REGION_FILE_NAME = "last_region.json"


def request_path(state_file: str | Path) -> Path:
    """Where the request file is."""
    return Path(state_file).with_name(REQUEST_FILE_NAME)


def write_request(state_file: str | Path, region: tuple[int, int, int, int] | None = None) -> Path:
    """Ask for a reading of the board (the teacher tapped).

    The file is written atomically, so the service never reads half of it.
    """
    target = request_path(state_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"at": time.time(), "region": list(region) if region else None}
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(temporary, target)
    LOGGER.info("A reading of the board was asked for")
    return target


def read_request(state_file: str | Path) -> dict[str, Any] | None:
    """The request of the teacher (``None`` when there is none)."""
    target = request_path(state_file)
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def clear_request(state_file: str | Path) -> None:
    """Take the request away (the service has done it)."""
    target = request_path(state_file)
    try:
        target.unlink()
    except OSError:
        pass


def region_path(state_file: str | Path) -> Path:
    """Where the area of the board is remembered."""
    return Path(state_file).with_name(REGION_FILE_NAME)


def remember_region(state_file: str | Path, region: tuple[int, int, int, int] | None) -> Path:
    """Remember the area of the board the teacher picked.

    After the first tap the key (``F8``) and the button of the floating
    window read **this** area - so the answer is about the writing and not
    about the whole screen.
    """
    target = region_path(state_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"region": list(region) if region else None}
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(temporary, target)
    return target


def read_region(state_file: str | Path) -> tuple[int, int, int, int] | None:
    """The area of the board the teacher picked last (``None`` when there is none)."""
    target = region_path(state_file)
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    region = payload.get("region") if isinstance(payload, dict) else None
    if not region or len(region) != 4:
        return None
    try:
        return tuple(int(value) for value in region)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def forget_region(state_file: str | Path) -> None:
    """Forget the area (the whole board is read again)."""
    try:
        region_path(state_file).unlink()
    except OSError:
        pass


__all__ = [
    "REGION_FILE_NAME",
    "REQUEST_FILE_NAME",
    "clear_request",
    "forget_region",
    "read_region",
    "read_request",
    "region_path",
    "remember_region",
    "request_path",
    "write_request",
]
