"""The background service of the board."""

import json
import time

from PIL import Image

from aieva.core.ocr.capture import Capture
from aieva.core.ocr.engines import MockOcr
from aieva.core.ocr.pipeline import OcrPipeline
from aieva.core.service.config import ServiceConfig
from aieva.core.service.runner import BackgroundService, result_path
from aieva.core.service.state import ServiceState


class FakeSource:
    """A source that always shows the same board."""

    name = "fake"

    def __init__(self, image: Image.Image | None = None) -> None:
        self.image = image or Image.new("RGB", (320, 240), (255, 255, 255))

    def available(self) -> bool:
        return True

    def grab(self) -> Capture:
        return Capture(
            image=self.image,
            box=(0, 0, self.image.width, self.image.height),
            source=self.name,
        )


def make_config(tmp_path, **changes) -> ServiceConfig:
    """A configuration that writes into the temporary folder."""
    values = {
        "source": "desktop",
        "poll_seconds": 0.05,
        "min_interval_seconds": 0.0,
        "change_threshold": 0.0,
        "outbox": tmp_path / "outbox",
        "state_file": tmp_path / "state.json",
        "captures_dir": tmp_path / "captures",
        "mock_ocr": True,
        "auto_solve": False,
        "auto_plot": False,
    }
    values.update(changes)
    return ServiceConfig(**values)


def test_a_reading_is_published(tmp_path) -> None:
    config = make_config(tmp_path)
    service = BackgroundService(config=config, source=FakeSource())
    run = service.run_once()
    assert run.ran is True
    assert run.plain == "x**2 + y**2 = 9"
    files = sorted((tmp_path / "outbox").glob("board-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["plain"] == "x**2 + y**2 = 9"
    assert result_path(config.state_file).is_file()


def test_the_state_remembers_the_reading(tmp_path) -> None:
    config = make_config(tmp_path)
    service = BackgroundService(config=config, source=FakeSource())
    service.run_once()
    state = ServiceState.load(config.state_file)
    assert state.runs == 1
    assert state.last_plain == "x**2 + y**2 = 9"
    assert state.status == "running"


def test_an_unchanged_board_is_not_read_twice(tmp_path) -> None:
    config = make_config(tmp_path, change_threshold=0.9)
    service = BackgroundService(config=config, source=FakeSource())
    assert service.run_once().ran is True
    second = service.run_once()
    assert second.ran is False
    assert "did not change" in second.reason


def test_the_service_solves_the_reading(tmp_path) -> None:
    config = make_config(tmp_path, auto_solve=True)
    pipeline = OcrPipeline(
        engines=[MockOcr(latex="x**2 - 4 = 0", plain="x**2 - 4 = 0")], use_cache=False
    )
    service = BackgroundService(config=config, source=FakeSource(), pipeline=pipeline)
    run = service.run_once()
    assert run.ran is True
    assert "2" in run.answer


def test_the_history_is_kept(tmp_path) -> None:
    config = make_config(tmp_path, change_threshold=0.0)
    source = FakeSource()
    service = BackgroundService(config=config, source=source)
    service.run_once()
    source.image = Image.new("RGB", (320, 240), (0, 0, 0))
    service.run_once()
    history = (tmp_path / "outbox" / "history.jsonl").read_text(encoding="utf-8")
    assert len(history.strip().splitlines()) == 2


def test_the_service_stops(tmp_path) -> None:
    config = make_config(tmp_path)
    service = BackgroundService(config=config, source=FakeSource())
    service.start()
    time.sleep(0.2)
    service.stop()
    assert service.is_running is False


def test_the_loop_survives_an_error(tmp_path) -> None:
    class BrokenSource(FakeSource):
        def grab(self) -> Capture:
            raise RuntimeError("no screen")

    config = make_config(tmp_path)
    service = BackgroundService(config=config, source=BrokenSource())
    service.start()
    time.sleep(0.2)
    service.stop()
    assert service.state.errors >= 1
    assert service.is_running is False


def test_the_listener_is_told(tmp_path) -> None:
    seen: list[dict] = []
    config = make_config(tmp_path)
    service = BackgroundService(config=config, source=FakeSource(), notifier=seen.append)
    service.run_once()
    assert len(seen) == 1
    assert seen[0]["plain"] == "x**2 + y**2 = 9"
