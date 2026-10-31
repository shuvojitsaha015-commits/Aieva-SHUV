"""The user settings of Phase 11 (headless, no Kivy)."""

from __future__ import annotations

import os

import pytest

from aieva.core.user_settings import (
    MAX_PALM_THRESHOLD,
    MAX_PEN_WIDTH,
    MIN_PALM_THRESHOLD,
    MIN_PEN_WIDTH,
    QUALITY_LEVELS,
    UserSettings,
    plot_quality,
)


def test_the_defaults():
    settings = UserSettings()
    assert settings.server_url == ""
    assert settings.quality == "low"
    assert settings.offline_mode is False
    assert settings.pen_width == 4.0
    assert settings.palm_rejection is True
    assert settings.palm_threshold == 60.0


def test_the_values_are_clamped():
    settings = UserSettings(pen_width=1000.0, palm_threshold=-5.0, quality="nonsense")
    assert settings.pen_width == MAX_PEN_WIDTH
    assert settings.palm_threshold == MIN_PALM_THRESHOLD
    assert settings.quality == "low"


def test_the_smallest_values_are_kept():
    settings = UserSettings(pen_width=0.0, palm_threshold=10_000.0)
    assert settings.pen_width == MIN_PEN_WIDTH
    assert settings.palm_threshold == MAX_PALM_THRESHOLD


def test_the_quality_levels():
    assert QUALITY_LEVELS == ("low", "normal", "high")
    assert plot_quality("low") == "low"
    assert plot_quality("normal") == "medium"
    assert plot_quality("high") == "high"
    assert plot_quality("something") == "medium"


def test_save_and_load(tmp_path):
    path = tmp_path / "user_settings.json"
    settings = UserSettings(
        server_url="http://board.local:8000/",
        quality="high",
        offline_mode=True,
        pen_width=8.0,
        palm_rejection=False,
        palm_threshold=90.0,
    )
    written = settings.save(path)
    assert written == path
    loaded = UserSettings.load(path)
    assert loaded.server_url == "http://board.local:8000"
    assert loaded.quality == "high"
    assert loaded.offline_mode is True
    assert loaded.pen_width == 8.0
    assert loaded.palm_rejection is False
    assert loaded.palm_threshold == 90.0


def test_a_missing_file_gives_the_defaults(tmp_path):
    settings = UserSettings.load(tmp_path / "nothing.json")
    assert settings.quality == "low"


def test_a_broken_file_gives_the_defaults(tmp_path):
    path = tmp_path / "user_settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert UserSettings.load(path).quality == "low"


def test_an_unknown_key_is_ignored(tmp_path):
    path = tmp_path / "user_settings.json"
    path.write_text('{"quality": "low", "unknown": 5}', encoding="utf-8")
    settings = UserSettings.load(path)
    assert settings.quality == "low"


def test_the_settings_reach_the_environment(tmp_path, monkeypatch):
    from aieva.config import get_settings

    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path))
    names = ("AIEVA_SERVER_URL", "AIEVA_QUALITY", "AIEVA_OFFLINE_MODE")
    old = {name: os.environ.get(name) for name in names}
    settings = UserSettings(server_url="http://192.168.1.10:8000", quality="low", offline_mode=True)
    try:
        values = settings.apply_to_environment()
        assert values["AIEVA_SERVER_URL"] == "http://192.168.1.10:8000"
        assert values["AIEVA_QUALITY"] == "low"
        assert values["AIEVA_OFFLINE_MODE"] == "true"
        assert os.environ["AIEVA_SERVER_URL"] == "http://192.168.1.10:8000"

        assert get_settings(reload=True).server_url == "http://192.168.1.10:8000"
        assert get_settings().offline_mode is True
    finally:
        # the environment and the cache have to show the old values again
        for name, value in old.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings(reload=True)


def test_the_path_is_inside_the_cache_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path))

    from aieva.config import get_settings

    get_settings(reload=True)
    path = UserSettings.path()
    assert path.parent == tmp_path
    assert path.name == "user_settings.json"


def test_to_dict():
    data = UserSettings().to_dict()
    assert set(data) == {
        "server_url",
        "quality",
        "offline_mode",
        "pen_width",
        "palm_rejection",
        "palm_threshold",
    }


def test_the_core_does_not_import_kivy():
    """The settings belong to the headless core."""
    import aieva.core.user_settings as module

    with open(module.__file__, encoding="utf-8") as handle:
        source = handle.read()
    assert "import kivy" not in source


@pytest.mark.parametrize("quality", ["low", "normal", "high"])
def test_every_quality_is_kept(quality):
    assert UserSettings(quality=quality).quality == quality
