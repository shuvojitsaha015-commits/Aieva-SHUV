"""Phase 1 smoke tests: the package imports and the settings load."""

from __future__ import annotations

import aieva
from aieva.config import Settings, get_settings, settings_from_env


def test_import_package() -> None:
    assert aieva.__version__


def test_settings_load() -> None:
    settings = get_settings(reload=True)
    assert isinstance(settings, Settings)
    assert settings.server_url.startswith("http")
    assert settings.cache_dir.name  # a Path, name depends on the environment


def test_settings_defaults_and_parsing() -> None:
    settings = settings_from_env(
        {
            "GEMINI_API_KEY": " abc ",
            "AIEVA_OFFLINE_MODE": "true",
            "AIEVA_MOCK_LLM": "1",
            "AIEVA_CACHE_DIR": "/tmp/aieva-test-cache",
        }
    )
    assert settings.gemini_api_key == "abc"
    assert settings.offline_mode is True
    assert settings.mock_llm is True
    assert settings.cloud_enabled is False  # offline wins


def test_errors_are_typed() -> None:
    from aieva.core.errors import AievaError, ParseError

    err = ParseError("bad input", detail="expected '='")
    assert isinstance(err, AievaError)
    assert err.message == "bad input"
    assert "expected" in str(err)
