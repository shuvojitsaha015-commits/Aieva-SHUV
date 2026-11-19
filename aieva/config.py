"""Typed application settings loaded from the environment / ``.env`` file.

Rules for this module:

* never hardcode a secret - everything comes from the environment;
* never raise at import time - a missing ``.env`` simply means "use defaults";
* never import Kivy (the core must stay headless-testable).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # pragma: no cover - python-dotenv is a hard requirement, but stay importable
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover

    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:  # type: ignore[misc]
        return False


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = REPO_ROOT / ".env"

_TRUE = {"1", "true", "yes", "on", "y"}
_FALSE = {"0", "false", "no", "off", "n"}


def _as_bool(value: str | None, default: bool = False) -> bool:
    """Convert an environment string to a bool, tolerating junk values."""
    if value is None:
        return default
    text = value.strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return default


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of the application configuration."""

    # --- LLM / cloud ---------------------------------------------------
    #: The first Gemini key (the old, simple way).
    gemini_api_key: str = ""
    #: **All** the Gemini keys - the first one is the one of
    #: ``gemini_api_key``. Several keys mean more quota and a fallback
    #: that stays inside Gemini (see :mod:`server.services.gemini`).
    gemini_api_keys: tuple[str, ...] = ()
    gemini_model: str = "gemini-3.8-flash"
    openai_api_key: str = ""
    wolfram_app_id: str = ""

    # --- connectivity --------------------------------------------------
    server_url: str = "http://127.0.0.1:8000"
    server_api_key: str = ""
    server_timeout: float = 120.0
    mock_llm: bool = False

    # --- behaviour -----------------------------------------------------
    offline_mode: bool = False
    cache_dir: Path = field(default_factory=lambda: Path(".aieva_cache"))
    cache_ttl_seconds: int = 24 * 60 * 60
    log_file: Path = field(default_factory=lambda: Path("aieva.log"))

    # --- ui ------------------------------------------------------------
    window_width: int = 1280
    window_height: int = 720
    quality: str = "normal"  # low | normal | high

    # --- derived helpers ------------------------------------------------
    @property
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def all_gemini_keys(self) -> tuple[str, ...]:
        """Every Gemini key, without the empty ones and without duplicates.

        The order is kept - the first key is the one that is tried first.
        """
        seen: list[str] = []
        for key in (self.gemini_api_key, *self.gemini_api_keys):
            value = key.strip()
            if value and value not in seen:
                seen.append(value)
        return tuple(seen)

    @property
    def cloud_enabled(self) -> bool:
        """Cloud calls are only allowed when we are online *and* have a key."""
        return not self.offline_mode and (self.has_gemini_key or self.mock_llm)

    def cache_path(self) -> Path:
        path = Path(self.cache_dir)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.mkdir(parents=True, exist_ok=True)
        return path


def _split_keys(value: str | None) -> tuple[str, ...]:
    """Split a list of keys (``a,b`` or ``a; b`` or one key).

    The keys are separated by a comma or a semicolon - a key itself never
    contains one of them.
    """
    if not value:
        return ()
    parts = value.replace(";", ",").split(",")
    return tuple(part.strip() for part in parts if part.strip())


def settings_from_env(env: dict[str, str] | None = None) -> Settings:
    """Build a :class:`Settings` from a mapping (defaults to ``os.environ``)."""
    src = dict(os.environ if env is None else env)
    return Settings(
        gemini_api_key=src.get("GEMINI_API_KEY", "").strip(),
        gemini_api_keys=_split_keys(src.get("GEMINI_API_KEYS", "")),
        gemini_model=src.get("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash",
        openai_api_key=src.get("OPENAI_API_KEY", "").strip(),
        wolfram_app_id=src.get("WOLFRAM_APP_ID", "").strip(),
        server_url=(src.get("AIEVA_SERVER_URL", "").strip() or "http://127.0.0.1:8000"),
        server_api_key=src.get("AIEVA_SERVER_KEY", "").strip(),
        server_timeout=float(src.get("AIEVA_SERVER_TIMEOUT", "120") or 120),
        mock_llm=_as_bool(src.get("AIEVA_MOCK_LLM"), False),
        offline_mode=_as_bool(src.get("AIEVA_OFFLINE_MODE"), False),
        cache_dir=Path(src.get("AIEVA_CACHE_DIR", ".aieva_cache")),
        cache_ttl_seconds=_as_int(src.get("AIEVA_CACHE_TTL"), 24 * 60 * 60),
        log_file=Path(src.get("AIEVA_LOG_FILE", "aieva.log")),
        window_width=_as_int(src.get("AIEVA_WINDOW_WIDTH"), 1280),
        window_height=_as_int(src.get("AIEVA_WINDOW_HEIGHT"), 720),
        quality=src.get("AIEVA_QUALITY", "normal").strip() or "normal",
    )


#: The cached settings (per ``.env`` file).
_SETTINGS_CACHE: dict[str | None, Settings] = {}


def get_settings(env_file: str | Path | None = None, reload: bool = False) -> Settings:
    """Return the process-wide settings, loading ``.env`` once.

    ``reload=True`` throws the cache away, so a changed environment (or a
    changed ``.env``) is picked up. The cache is **not** an ``lru_cache``:
    the flag has to be able to clear the cache *before* the lookup - with
    ``lru_cache`` a second call with the same arguments would return the
    old value without ever running the body of the function.
    """
    if reload:
        _SETTINGS_CACHE.clear()
    key = str(env_file) if env_file is not None else None
    if key not in _SETTINGS_CACHE:
        path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
        if path.is_file():
            load_dotenv(path, override=False)
        _SETTINGS_CACHE[key] = settings_from_env()
    return _SETTINGS_CACHE[key]


def clear_settings_cache() -> None:
    """Throw the cached settings away."""
    _SETTINGS_CACHE.clear()


__all__ = [
    "DEFAULT_ENV_FILE",
    "REPO_ROOT",
    "Settings",
    "clear_settings_cache",
    "get_settings",
    "settings_from_env",
]
