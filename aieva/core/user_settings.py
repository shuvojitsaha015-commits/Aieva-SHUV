"""The settings the user changes in the application.

The environment (``.env``) configures the **deployment**; this file holds the
settings a teacher changes while the application is running (the server URL,
the quality, the offline mode, the pen thickness and the palm rejection).

The settings are stored as JSON in the cache directory and are applied to the
environment when the application starts, so every part of Aieva sees them.

The module never imports Kivy - it is part of the headless core.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The name of the file inside the cache directory.
FILE_NAME = "user_settings.json"

#: The quality levels of the renderer.
QUALITY_LEVELS: tuple[str, ...] = ("low", "normal", "high")

#: The quality that is used when the user did not choose one.
#: ``low`` keeps the 3D renderer fast on a board (the mesh is 30x30).
DEFAULT_QUALITY = "low"

#: How the quality of the user maps to the quality of the 3D renderer.
PLOT_QUALITY: dict[str, str] = {"low": "low", "normal": "medium", "high": "high"}


def plot_quality(quality: str) -> str:
    """The quality of the 3D renderer for a quality of the user."""
    return PLOT_QUALITY.get((quality or "").strip().lower(), "medium")


#: The smallest and the biggest pen width (in pixels).
MIN_PEN_WIDTH = 1.0
MAX_PEN_WIDTH = 24.0

#: The smallest and the biggest palm threshold (in pixels).
MIN_PALM_THRESHOLD = 10.0
MAX_PALM_THRESHOLD = 200.0


def _clamp(value: float, low: float, high: float) -> float:
    """Keep a number inside its range."""
    return max(low, min(high, float(value)))


@dataclass
class UserSettings:
    """The settings a user can change in the application."""

    server_url: str = ""
    quality: str = "low"
    offline_mode: bool = False
    pen_width: float = 4.0
    palm_rejection: bool = True
    palm_threshold: float = 60.0
    #: Watch the board in the background while the application is open.
    background_service: bool = True

    def __post_init__(self) -> None:
        self.quality = (self.quality or "low").strip().lower()
        if self.quality not in QUALITY_LEVELS:
            self.quality = "low"
        self.pen_width = _clamp(self.pen_width, MIN_PEN_WIDTH, MAX_PEN_WIDTH)
        self.palm_threshold = _clamp(self.palm_threshold, MIN_PALM_THRESHOLD, MAX_PALM_THRESHOLD)
        self.server_url = (self.server_url or "").strip().rstrip("/")
        self.offline_mode = bool(self.offline_mode)
        self.background_service = bool(self.background_service)

    # ------------------------------------------------------------------ api
    @classmethod
    def path(cls, cache_dir: str | Path | None = None) -> Path:
        """Where the settings are stored."""
        if cache_dir is None:
            from aieva.config import get_settings

            base = Path(get_settings().cache_dir)
        else:
            base = Path(cache_dir)
        if not base.is_absolute():
            base = Path.cwd() / base
        return base / FILE_NAME

    @classmethod
    def load(cls, path: str | Path | None = None) -> UserSettings:
        """Read the settings (the defaults when the file is missing)."""
        target = Path(path) if path is not None else cls.path()
        if not target.is_file():
            return cls()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - a broken file must not crash
            LOGGER.info("The user settings could not be read: %s", exc)
            return cls()
        if not isinstance(data, dict):
            return cls()
        known = {item.name for item in fields(cls)}
        clean = {key: value for key, value in data.items() if key in known}
        try:
            return cls(**clean)
        except TypeError:
            return cls()

    def save(self, path: str | Path | None = None) -> Path:
        """Write the settings and return the file."""
        target = Path(path) if path is not None else self.path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return target

    def apply_to_environment(self) -> dict[str, str]:
        """Put the settings into the environment (and refresh the settings)."""
        values: dict[str, str] = {}
        if self.server_url:
            values["AIEVA_SERVER_URL"] = self.server_url
        values["AIEVA_QUALITY"] = self.quality
        values["AIEVA_OFFLINE_MODE"] = "true" if self.offline_mode else "false"
        os.environ.update(values)
        from aieva.config import get_settings

        get_settings(reload=True)
        return values

    def to_dict(self) -> dict[str, Any]:
        """The settings as a plain dictionary."""
        return asdict(self)


__all__ = [
    "DEFAULT_QUALITY",
    "FILE_NAME",
    "PLOT_QUALITY",
    "MAX_PALM_THRESHOLD",
    "MAX_PEN_WIDTH",
    "MIN_PALM_THRESHOLD",
    "MIN_PEN_WIDTH",
    "QUALITY_LEVELS",
    "UserSettings",
    "plot_quality",
]
