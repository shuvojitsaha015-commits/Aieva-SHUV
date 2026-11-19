"""The status file of the background service.

The service writes a small JSON file with its state, so that

* the teacher can see what the service is doing (``aieva-service status``),
* the window of the teacher can show it,
* a second instance knows that the service is already running.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The states the service can be in.
STATUSES: tuple[str, ...] = ("stopped", "starting", "running", "error")

#: The name of the service.
SERVICE_NAME = "aieva-board-service"


@dataclass
class ServiceState:
    """What the service is doing right now."""

    status: str = "stopped"
    service: str = SERVICE_NAME
    version: str = "1.0.0"
    pid: int = 0
    started_at: float = 0.0
    updated_at: float = 0.0
    runs: int = 0
    errors: int = 0
    last_error: str = ""
    last_run_at: float = 0.0
    last_source: str = ""
    last_latex: str = ""
    last_plain: str = ""
    last_answer: str = ""
    last_plot: str = ""
    last_capture: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ api
    def to_dict(self) -> dict[str, Any]:
        """The state as a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ServiceState:
        """Read a state back (the unknown fields land in ``extra``)."""
        known = set(cls.__dataclass_fields__)
        clean = {key: value for key, value in payload.items() if key in known}
        extra = {key: value for key, value in payload.items() if key not in known}
        state = cls(**clean)  # type: ignore[arg-type]
        state.extra = extra
        return state

    def save(self, path: str | Path) -> Path:
        """Write the state (the write is atomic - a half file is never read)."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = time.time()
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(temporary, target)
        return target

    @classmethod
    def load(cls, path: str | Path) -> ServiceState:
        """Read the state (the default state when the file is missing)."""
        target = Path(path)
        if not target.is_file():
            return cls()
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            LOGGER.info("The state file could not be read: %s", exc)
            return cls()
        if not isinstance(payload, dict):
            return cls()
        return cls.from_dict(payload)

    def uptime_seconds(self, now: float | None = None) -> float:
        """How long the service has been running."""
        if not self.started_at:
            return 0.0
        return max(0.0, (now if now is not None else time.time()) - self.started_at)

    def is_running(self) -> bool:
        """``True`` while the service is watching the board."""
        return self.status in ("starting", "running")


#: The name of the file that asks the service to stop.
STOP_FILE_NAME = "stop_request"


def stop_request_path(state_file: str | Path) -> Path:
    """Where the stop request is written."""
    return Path(state_file).with_name(STOP_FILE_NAME)


def write_stop_request(state_file: str | Path) -> Path:
    """Ask the background service to stop.

    The file is written atomically, so the service never reads half of it.
    """
    target = stop_request_path(state_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(str(time.time()), encoding="utf-8")
    os.replace(temporary, target)
    return target


def read_stop_request(state_file: str | Path) -> bool:
    """``True`` when the service was asked to stop."""
    return stop_request_path(state_file).is_file()


def clear_stop_request(state_file: str | Path) -> None:
    """Take the stop request away (the service has done it)."""
    try:
        stop_request_path(state_file).unlink()
    except OSError:
        pass


__all__ = [
    "SERVICE_NAME",
    "STATUSES",
    "STOP_FILE_NAME",
    "ServiceState",
    "clear_stop_request",
    "read_stop_request",
    "stop_request_path",
    "write_stop_request",
]
