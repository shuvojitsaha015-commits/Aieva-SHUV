"""The settings of the background service."""

from pathlib import Path

from aieva.core.service.config import SOURCES, ServiceConfig


def test_the_defaults_are_safe() -> None:
    config = ServiceConfig()
    assert config.source == "auto"
    assert config.poll_seconds == 2.0
    assert config.min_interval_seconds == 2.0
    assert config.change_threshold > 0
    assert config.max_runs_per_minute >= 1
    assert config.auto_solve is True
    assert config.auto_plot is True
    assert config.overlay is False
    assert config.mock_ocr is False


def test_the_environment_is_read() -> None:
    env = {
        "AIEVA_SERVICE_SOURCE": "folder",
        "AIEVA_SERVICE_INTERVAL": "5",
        "AIEVA_SERVICE_OVERLAY": "true",
        "AIEVA_SERVICE_SOLVE": "no",
        "AIEVA_SERVICE_FOLDER": "inbox",
        "AIEVA_SERVICE_OUTBOX": "outbox",
        "AIEVA_SERVICE_MOCK": "1",
        "AIEVA_SERVER_URL": "http://board:8000/",
    }
    config = ServiceConfig.from_env(env)
    assert config.source == "folder"
    assert config.poll_seconds == 5.0
    assert config.overlay is True
    assert config.auto_solve is False
    assert config.folder == Path("inbox")
    assert config.outbox == Path("outbox")
    assert config.mock_ocr is True
    assert config.server_url == "http://board:8000"


def test_an_unknown_source_falls_back_to_auto() -> None:
    assert ServiceConfig(source="hologram").source == "auto"
    assert "auto" in SOURCES


def test_the_values_are_clamped() -> None:
    config = ServiceConfig(
        poll_seconds=0.0, change_threshold=5.0, max_runs_per_minute=0, overlay_seconds=0.0
    )
    assert config.poll_seconds >= 0.2
    assert config.change_threshold == 1.0
    assert config.max_runs_per_minute == 1
    assert config.overlay_seconds >= 1.0


def test_replaced_makes_a_copy() -> None:
    config = ServiceConfig()
    other = config.replaced(source="desktop")
    assert other.source == "desktop"
    assert config.source == "auto"


def test_the_configuration_can_be_written_down() -> None:
    data = ServiceConfig().to_dict()
    assert data["source"] == "auto"
    assert isinstance(data["folder"], str)
