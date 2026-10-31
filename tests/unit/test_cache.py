"""Phase 2: the on-disk cache."""

from __future__ import annotations

import time
from pathlib import Path

from aieva.core.cache import DiskCache


def test_set_and_get_json(tmp_path: Path) -> None:
    cache = DiskCache(cache_dir=tmp_path)
    cache.set("ocr", "abc", {"latex": "x^2", "confidence": 0.9})
    assert cache.get("ocr", "abc") == {"latex": "x^2", "confidence": 0.9}


def test_set_and_get_bytes(tmp_path: Path) -> None:
    cache = DiskCache(cache_dir=tmp_path)
    cache.set("figs", "abc", b"\x89PNG\r\n")
    assert cache.get_bytes("figs", "abc") == b"\x89PNG\r\n"


def test_missing_key_returns_default(tmp_path: Path) -> None:
    cache = DiskCache(cache_dir=tmp_path)
    assert cache.get("ocr", "nope") is None
    assert cache.get("ocr", "nope", default="fallback") == "fallback"


def test_ttl_expiry(tmp_path: Path) -> None:
    cache = DiskCache(cache_dir=tmp_path, ttl_seconds=1)
    cache.set("ocr", "abc", "value", ttl_seconds=1)
    assert cache.get("ocr", "abc") == "value"
    # rewrite the envelope with an expired timestamp
    path = cache.path_for("ocr", "abc")
    import json

    envelope = json.loads(path.read_text())
    envelope["expires"] = time.time() - 10
    path.write_text(json.dumps(envelope))
    assert cache.get("ocr", "abc") is None


def test_clear(tmp_path: Path) -> None:
    cache = DiskCache(cache_dir=tmp_path)
    cache.set("a", "1", 1)
    cache.set("b", "2", 2)
    assert cache.clear("a") == 1
    assert cache.get("a", "1") is None
    assert cache.get("b", "2") == 2
    assert cache.clear() == 1


def test_corrupted_entry_is_ignored(tmp_path: Path) -> None:
    cache = DiskCache(cache_dir=tmp_path)
    cache.set("ocr", "abc", "value")
    cache.path_for("ocr", "abc").write_text("{not json")
    assert cache.get("ocr", "abc") is None


def test_stats(tmp_path: Path) -> None:
    cache = DiskCache(cache_dir=tmp_path)
    cache.set("ocr", "a", 1)
    stats = cache.stats()
    assert stats["entries"] == 1
    assert stats["namespaces"]["ocr"] == 1


def test_keys_are_hashed(tmp_path: Path) -> None:
    cache = DiskCache(cache_dir=tmp_path)
    path = cache.path_for("ocr", "x^2 + y")
    assert "x^2" not in path.name
    assert path.suffix == ".json"
