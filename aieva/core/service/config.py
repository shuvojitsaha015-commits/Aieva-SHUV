"""The settings of the background board service.

The service is the part of Aieva that runs **in the background of the smart
board**: it looks at the board, notices when something new was written, reads
the mathematics with the OCR and (optionally) solves and draws it - without
anybody having to touch the computer.

The settings come from the environment (``.env``) or from the
:class:`~aieva.core.user_settings.UserSettings` of the teacher, so the same
build runs on a development laptop and on the board.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: The capture sources the service understands.
SOURCES: tuple[str, ...] = ("auto", "desktop", "folder")

_TRUE = {"1", "true", "yes", "on", "y"}
_FALSE = {"0", "false", "no", "off", "n"}


def _as_bool(value: object, default: bool = False) -> bool:
    """Convert a value to a bool, tolerating junk."""
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return default


def _as_float(value: object, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _as_int(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def resolve(path: str | Path) -> Path:
    """An absolute path (relative paths belong to the working directory)."""
    target = Path(path)
    return target if target.is_absolute() else Path.cwd() / target


@dataclass(frozen=True)
class ServiceConfig:
    """Everything the background service needs to know."""

    # --- what is watched -------------------------------------------------
    #: ``auto`` (the desktop screen, otherwise a folder), ``desktop`` or ``folder``.
    source: str = "auto"
    #: How often the board is looked at (seconds).
    poll_seconds: float = 2.0
    #: The shortest time between two readings of the board.
    min_interval_seconds: float = 2.0
    #: How much the board has to change before it is read again (0 - 1).
    change_threshold: float = 0.004
    #: The safety limit - no more than this many readings per minute.
    max_runs_per_minute: int = 12

    # --- where everything goes -------------------------------------------
    #: The folder with the pictures of the board (the ``folder`` source).
    folder: Path = Path("ocr_inbox")
    #: Where the results are written (one JSON file per reading).
    outbox: Path = Path("ocr_outbox")
    #: The status file of the service.
    state_file: Path = Path(".aieva_cache/service_state.json")
    #: Where the captured pictures are kept.
    captures_dir: Path = Path(".aieva_cache/captures")
    #: The log file of the service.
    log_file: Path = Path("aieva.log")

    # --- what the service does with the reading --------------------------
    #: Solve the equation right away.
    auto_solve: bool = True
    #: Draw the graph of the equation.
    auto_plot: bool = True
    #: Show the reading in a small window above the board.
    overlay: bool = False
    #: How long the window stays visible (seconds).
    overlay_seconds: float = 8.0
    #: Use the mock OCR (no cloud, no key - for the tests and the demo).
    mock_ocr: bool = False
    #: How many readings are kept in the history.
    keep_history: int = 200

    # --- the server (the "fog") ------------------------------------------
    server_url: str = "http://127.0.0.1:8000"
    server_api_key: str = ""
    server_timeout: float = 30.0

    def __post_init__(self) -> None:
        set_ = object.__setattr__
        source = (self.source or "auto").strip().lower()
        set_(self, "source", source if source in SOURCES else "auto")
        set_(self, "poll_seconds", max(0.2, _as_float(self.poll_seconds, 2.0)))
        set_(self, "min_interval_seconds", max(0.0, _as_float(self.min_interval_seconds, 2.0)))
        set_(self, "change_threshold", min(1.0, max(0.0, _as_float(self.change_threshold, 0.004))))
        set_(self, "max_runs_per_minute", max(1, _as_int(self.max_runs_per_minute, 12)))
        set_(self, "auto_solve", bool(self.auto_solve))
        set_(self, "auto_plot", bool(self.auto_plot))
        set_(self, "overlay", bool(self.overlay))
        set_(self, "overlay_seconds", max(1.0, _as_float(self.overlay_seconds, 8.0)))
        set_(self, "mock_ocr", bool(self.mock_ocr))
        set_(self, "keep_history", max(1, _as_int(self.keep_history, 200)))
        set_(self, "server_timeout", max(1.0, _as_float(self.server_timeout, 30.0)))
        set_(self, "folder", Path(self.folder))
        set_(self, "outbox", Path(self.outbox))
        set_(self, "state_file", Path(self.state_file))
        set_(self, "captures_dir", Path(self.captures_dir))
        set_(self, "log_file", Path(self.log_file))
        set_(self, "server_url", (self.server_url or "").strip().rstrip("/"))
        set_(self, "server_api_key", (self.server_api_key or "").strip())

    # ------------------------------------------------------------------ api
    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> ServiceConfig:
        """Build the configuration from the environment (``.env``)."""
        src = dict(os.environ if env is None else env)
        return cls(
            source=src.get("AIEVA_SERVICE_SOURCE", "auto"),
            poll_seconds=_as_float(src.get("AIEVA_SERVICE_INTERVAL"), 2.0),
            min_interval_seconds=_as_float(src.get("AIEVA_SERVICE_MIN_INTERVAL"), 2.0),
            change_threshold=_as_float(src.get("AIEVA_SERVICE_THRESHOLD"), 0.004),
            max_runs_per_minute=_as_int(src.get("AIEVA_SERVICE_MAX_RUNS"), 12),
            folder=src.get("AIEVA_SERVICE_FOLDER", src.get("AIEVA_OCR_INBOX", "ocr_inbox")),
            outbox=src.get("AIEVA_SERVICE_OUTBOX", src.get("AIEVA_OCR_OUTBOX", "ocr_outbox")),
            state_file=src.get("AIEVA_SERVICE_STATE", ".aieva_cache/service_state.json"),
            captures_dir=src.get("AIEVA_SERVICE_CAPTURES", ".aieva_cache/captures"),
            log_file=src.get("AIEVA_LOG_FILE", "aieva.log"),
            auto_solve=_as_bool(src.get("AIEVA_SERVICE_SOLVE"), True),
            auto_plot=_as_bool(src.get("AIEVA_SERVICE_PLOT"), True),
            overlay=_as_bool(src.get("AIEVA_SERVICE_OVERLAY"), False),
            overlay_seconds=_as_float(src.get("AIEVA_SERVICE_OVERLAY_SECONDS"), 8.0),
            mock_ocr=_as_bool(src.get("AIEVA_SERVICE_MOCK"), False),
            keep_history=_as_int(src.get("AIEVA_SERVICE_HISTORY"), 200),
            server_url=src.get("AIEVA_SERVER_URL", "http://127.0.0.1:8000"),
            server_api_key=src.get("AIEVA_SERVER_KEY", ""),
            server_timeout=_as_float(src.get("AIEVA_SERVER_TIMEOUT"), 30.0),
        )

    def to_dict(self) -> dict[str, object]:
        """The configuration as a plain dictionary (for the logs)."""
        data = {key: getattr(self, key) for key in self.__dataclass_fields__}
        for key, value in list(data.items()):
            if isinstance(value, Path):
                data[key] = str(value)
        return data

    def replaced(self, **changes: object) -> ServiceConfig:
        """A copy with some values changed."""
        values = {key: getattr(self, key) for key in self.__dataclass_fields__}
        values.update(changes)
        return ServiceConfig(**values)  # type: ignore[arg-type]


__all__ = ["SOURCES", "ServiceConfig", "resolve"]
