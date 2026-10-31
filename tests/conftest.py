"""Shared pytest fixtures for the Aieva test-suite."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("AIEVA_OFFLINE_MODE", "true")
os.environ.setdefault("AIEVA_MOCK_LLM", "true")


@pytest.fixture(scope="session", autouse=True)
def virtual_display():
    """Start a virtual X server when no display is available (headless CI)."""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        yield None
        return
    xvfb = shutil.which("Xvfb")
    if xvfb is None:
        yield None
        return
    process = subprocess.Popen(
        [xvfb, ":99", "-screen", "0", "1280x720x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["DISPLAY"] = ":99"
    time.sleep(1.5)
    try:
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "fixtures"


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path_factory, monkeypatch):
    """Every test gets its own cache directory so nothing leaks between runs."""
    cache_dir = tmp_path_factory.mktemp("aieva_cache")
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(cache_dir))
    yield cache_dir


@pytest.fixture
def has_display() -> bool:
    """True when a real (or virtual) display is available for Kivy."""
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
