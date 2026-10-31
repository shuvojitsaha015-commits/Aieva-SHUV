"""A small hash keyed on-disk cache.

Used for OCR results, rendered figures and LLM explanations so that repeated
questions on a classroom board are instant.

The cache is *best effort*: a corrupted or expired entry is simply ignored.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from aieva.config import get_settings

DEFAULT_TTL_SECONDS = 24 * 60 * 60


class DiskCache:
    """Stores JSON-serialisable values and byte blobs on disk."""

    def __init__(self, cache_dir: str | Path | None = None, ttl_seconds: int | None = None) -> None:
        settings = get_settings()
        base = Path(cache_dir) if cache_dir is not None else Path(settings.cache_dir)
        if not base.is_absolute():
            base = Path.cwd() / base
        self.cache_dir = base
        self.ttl_seconds = int(
            ttl_seconds if ttl_seconds is not None else settings.cache_ttl_seconds
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- internals
    def _namespace_dir(self, namespace: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in namespace) or "default"
        path = self.cache_dir / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _key_hash(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def path_for(self, namespace: str, key: str) -> Path:
        """The file that stores ``key`` inside ``namespace``."""
        return self._namespace_dir(namespace) / f"{self._key_hash(key)}.json"

    # ------------------------------------------------------------------- API
    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        """Return the cached value or ``default`` when missing / expired."""
        path = self.path_for(namespace, key)
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, ValueError):
            return default
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            return default
        if not isinstance(envelope, dict):
            return default
        expires = envelope.get("expires")
        if expires is not None and float(expires) < time.time():
            return default
        payload = envelope.get("payload")
        if envelope.get("encoding") == "base64":
            try:
                return base64.b64decode(payload)
            except (ValueError, TypeError):
                return default
        return payload

    def set(self, namespace: str, key: str, value: Any, ttl_seconds: int | None = None) -> Path:
        """Store ``value`` under ``namespace``/``key`` and return the file path."""
        ttl = int(ttl_seconds if ttl_seconds is not None else self.ttl_seconds)
        encoding = None
        payload: Any = value
        if isinstance(value, (bytes, bytearray)):
            encoding = "base64"
            payload = base64.b64encode(bytes(value)).decode("ascii")
        envelope = {
            "namespace": namespace,
            "key_hash": self._key_hash(key),
            "created": time.time(),
            "expires": time.time() + ttl if ttl > 0 else None,
            "encoding": encoding,
            "payload": payload,
        }
        path = self.path_for(namespace, key)
        self._atomic_write(path, json.dumps(envelope, ensure_ascii=False))
        return path

    def get_bytes(self, namespace: str, key: str, default: bytes | None = None) -> bytes | None:
        """Convenience wrapper returning raw bytes."""
        value = self.get(namespace, key, default=None)
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        return default

    def clear(self, namespace: str | None = None) -> int:
        """Remove cached entries. Returns the number of deleted files."""
        removed = 0
        if namespace is None:
            targets = [p for p in self.cache_dir.iterdir() if p.is_dir()]
        else:
            targets = [self._namespace_dir(namespace)]
        for target in targets:
            for item in target.glob("*.json"):
                try:
                    item.unlink()
                    removed += 1
                except OSError:
                    continue
            try:
                if target.exists() and not any(target.iterdir()):
                    target.rmdir()
            except OSError:
                pass
        return removed

    def stats(self) -> dict[str, Any]:
        """A small summary, handy for the settings screen."""
        namespaces: dict[str, int] = {}
        total = 0
        for directory in self.cache_dir.glob("*"):
            if not directory.is_dir():
                continue
            count = len(list(directory.glob("*.json")))
            namespaces[directory.name] = count
            total += count
        return {"cache_dir": str(self.cache_dir), "entries": total, "namespaces": namespaces}

    # --------------------------------------------------------------- private
    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(text)
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


_CACHE: DiskCache | None = None


def get_cache() -> DiskCache:
    """Return the process wide cache (created on first use)."""
    global _CACHE
    if _CACHE is None:
        _CACHE = DiskCache()
    return _CACHE


#: The namespace of the rendered pictures.
RENDER_NAMESPACE = "renders"


def render_key(*parts: Any) -> str:
    """The key of a rendered picture."""
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def cached_render(key: str, build: Any) -> bytes:
    """The PNG of a rendered picture - from the cache when it is there.

    ``build`` is a callable that returns the PNG bytes; it is only called
    when the picture is not cached yet.
    """
    cache = get_cache()
    stored = cache.get_bytes(RENDER_NAMESPACE, key)
    if stored:
        return stored
    png = build()
    if png:
        cache.set(RENDER_NAMESPACE, key, png.decode("latin-1"))
    return png


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "RENDER_NAMESPACE",
    "DiskCache",
    "cached_render",
    "get_cache",
    "render_key",
]
