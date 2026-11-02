"""The data of the floating window above the board.

The service writes the last reading into a small JSON file - this module
knows how to read it and how to make it short and readable. The window
itself lives in the user interface
(:mod:`aieva.ui.board_overlay`), because it needs Kivy - the core stays
headless.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


def read_result(path: str | Path) -> dict[str, Any] | None:
    """The last result of the service (``None`` when there is none)."""
    target = Path(path)
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        LOGGER.debug("The result file could not be read: %s", exc)
        return None
    return payload if isinstance(payload, dict) else None


def result_stamp(payload: dict[str, Any]) -> str:
    """A short key that changes when a new result arrives."""
    reading = payload.get("plain") or payload.get("latex") or ""
    return f"{payload.get('created_at')}|{reading}"


def pretty(text: str) -> str:
    """A short, readable form of the reading (for the board)."""
    result = (text or "").strip()
    result = result.replace("\\sqrt", "√").replace("sqrt", "√")
    result = result.replace("\\pi", "π").replace("pi", "π")
    result = result.replace("\\cdot", "·").replace("**", "^").replace("*", "·")
    result = result.replace("^2", "²").replace("^3", "³")
    return result.strip()


__all__ = ["pretty", "read_result", "result_stamp"]
