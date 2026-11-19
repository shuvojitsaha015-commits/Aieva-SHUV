"""The request of the teacher reaches the background service."""

from __future__ import annotations

import time
from pathlib import Path

from aieva.core.service.config import ServiceConfig
from aieva.core.service.runner import BackgroundService, result_path
from aieva.core.service.scan import write_request


class FakeCapture:
    """A picture of the board."""

    def __init__(self, image) -> None:
        self.image = image
        self.source = "fake"

    def crop(self, region):
        return self


class FakeSource:
    """A source that always gives the same picture."""

    def __init__(self, image) -> None:
        self.image = image
        self.grabs = 0

    def available(self) -> bool:
        return True

    def grab(self):
        self.grabs += 1
        return FakeCapture(self.image)


class FakePipeline:
    """An OCR that always reads the same thing."""

    def __init__(self, text: str = "x = 2") -> None:
        self.text = text
        self.calls = 0

    def run(self, image, use_cache=None):
        from aieva.core.ocr.engines import OcrResult

        self.calls += 1
        return OcrResult(latex=self.text, plain=self.text, engine="fake")


def _image():
    from PIL import Image

    return Image.new("RGB", (40, 30), "white")


def _config(tmp_path: Path) -> ServiceConfig:
    return ServiceConfig(
        source="folder",
        poll_seconds=0.2,
        min_interval_seconds=0.0,
        max_runs_per_minute=60,
        state_file=tmp_path / "state.json",
        outbox=tmp_path / "outbox",
        captures_dir=tmp_path / "captures",
        auto_plot=False,
    )


def test_a_scan_can_be_started_by_hand(tmp_path) -> None:
    pipeline = FakePipeline()
    service = BackgroundService(
        config=_config(tmp_path), source=FakeSource(_image()), pipeline=pipeline
    )
    run = service.scan_now()
    assert run.ran is True
    assert run.plain == "x = 2"
    assert pipeline.calls == 1


def test_the_request_of_the_teacher_is_served(tmp_path) -> None:
    pipeline = FakePipeline()
    service = BackgroundService(
        config=_config(tmp_path), source=FakeSource(_image()), pipeline=pipeline
    )
    write_request(service.config.state_file)
    service.start()
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and pipeline.calls == 0:
            time.sleep(0.05)
    finally:
        service.stop()
    assert pipeline.calls >= 1


def test_the_result_is_written_for_the_window(tmp_path) -> None:
    service = BackgroundService(
        config=_config(tmp_path), source=FakeSource(_image()), pipeline=FakePipeline()
    )
    service.scan_now()
    target = result_path(service.config.state_file)
    assert target.is_file()
    import json

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload.get("plain") == "x = 2"


def test_the_area_of_the_board_is_used(tmp_path) -> None:
    service = BackgroundService(
        config=_config(tmp_path), source=FakeSource(_image()), pipeline=FakePipeline()
    )
    run = service.scan_now(region=(1, 2, 3, 4))
    assert run.ran is True


def test_the_area_the_teacher_picked_is_used_again(tmp_path) -> None:
    """After the first tap the key reads the same part of the board."""
    from aieva.core.service.scan import remember_region

    cropped: list[tuple[int, int, int, int] | None] = []

    class WatchingCapture(FakeCapture):
        def crop(self, region):
            cropped.append(region)
            return self

    class WatchingSource(FakeSource):
        def grab(self):
            return WatchingCapture(self.image)

    config = _config(tmp_path)
    service = BackgroundService(
        config=config, source=WatchingSource(_image()), pipeline=FakePipeline()
    )
    remember_region(config.state_file, (5, 6, 7, 8))
    service.scan_now()
    assert cropped == [(5, 6, 7, 8)]


def test_without_an_area_the_whole_board_is_read(tmp_path) -> None:
    cropped: list[tuple[int, int, int, int] | None] = []

    class WatchingCapture(FakeCapture):
        def crop(self, region):
            cropped.append(region)
            return self

    class WatchingSource(FakeSource):
        def grab(self):
            return WatchingCapture(self.image)

    config = _config(tmp_path)
    service = BackgroundService(
        config=config, source=WatchingSource(_image()), pipeline=FakePipeline()
    )
    service.scan_now()
    assert cropped == []
