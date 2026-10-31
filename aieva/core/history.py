"""Local JSON history of the equations the user worked with.

There is no database in v1 - a single JSON file inside the cache directory is
enough and it keeps the app usable without any permissions on Android.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aieva.config import get_settings

DEFAULT_LIMIT = 50


@dataclass
class HistoryEntry:
    """One remembered equation."""

    raw: str
    kind: str = "text"
    latex: str | None = None
    source: str = "manual"
    #: The subject plugin the entry belongs to ("math", later "biology", ...).
    subject: str = "math"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "kind": self.kind,
            "latex": self.latex,
            "source": self.source,
            "subject": self.subject,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryEntry:
        return cls(
            raw=str(data.get("raw", "")),
            kind=str(data.get("kind", "text")),
            latex=data.get("latex"),
            source=str(data.get("source", "manual")),
            subject=str(data.get("subject", "math")),
            timestamp=float(data.get("timestamp", 0.0)),
        )


class History:
    """A tiny append-only store for the equation history."""

    def __init__(self, path: str | Path | None = None, limit: int = DEFAULT_LIMIT) -> None:
        if path is None:
            base = Path(get_settings().cache_dir)
            if not base.is_absolute():
                base = Path.cwd() / base
            path = base / "history.json"
        self.path = Path(path)
        self.limit = limit

    # ------------------------------------------------------------------ API
    def add(
        self,
        raw: str,
        kind: str = "text",
        latex: str | None = None,
        source: str = "manual",
        subject: str = "math",
    ) -> HistoryEntry:
        """Remember an equation (most recent first)."""
        entry = HistoryEntry(raw=raw, kind=kind, latex=latex, source=source, subject=subject)
        entries = [item for item in self.entries() if item.raw != raw]
        entries.insert(0, entry)
        self._write(entries[: self.limit])
        return entry

    def entries(self) -> list[HistoryEntry]:
        """Every remembered equation, most recent first."""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except (OSError, ValueError):
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [HistoryEntry.from_dict(item) for item in data if isinstance(item, dict)]

    def recent(self, count: int = 10, subject: str | None = None) -> list[HistoryEntry]:
        """The ``count`` most recent entries (optionally of one subject)."""
        entries = self.entries()
        if subject:
            entries = [entry for entry in entries if entry.subject == subject]
        return entries[:count]

    def clear(self) -> None:
        """Forget everything."""
        self._write([])

    # ------------------------------------------------------------- internals
    def _write(self, entries: list[HistoryEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([entry.to_dict() for entry in entries], indent=2)
        self.path.write_text(payload, encoding="utf-8")


__all__ = ["DEFAULT_LIMIT", "History", "HistoryEntry"]
