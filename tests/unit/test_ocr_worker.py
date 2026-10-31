"""Phase 8: the background OCR worker and the folder watcher."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from PIL import Image

from aieva.core.ocr.engines import MockOcr
from aieva.core.ocr.pipeline import OcrPipeline
from aieva.core.ocr.worker import OcrWatcher, OcrWorker, main


def _image(path: Path, colour: str = "white") -> Path:
    image = Image.new("RGB", (120, 60), colour)
    image.save(path)
    return path


def test_the_worker_does_not_block_the_caller(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    from aieva.config import get_settings

    get_settings(reload=True)

    worker = OcrWorker(pipeline=OcrPipeline(engines=[MockOcr(latex="x^2", plain="x**2")]))
    started = time.perf_counter()
    worker.submit(Image.new("RGB", (20, 20)))
    elapsed = time.perf_counter() - started
    assert elapsed < 0.5  # the call returned immediately
    worker.stop()


def test_the_worker_calls_the_callback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    from aieva.config import get_settings

    get_settings(reload=True)

    done = threading.Event()
    answers: list[str] = []

    def on_result(result) -> None:
        answers.append(result.plain)
        done.set()

    worker = OcrWorker(pipeline=OcrPipeline(engines=[MockOcr(latex="x^2", plain="x**2")]))
    worker.submit(Image.new("RGB", (20, 20)), on_result)
    assert done.wait(15)
    worker.stop()
    assert answers == ["x**2"]


def test_the_worker_counts_the_jobs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    from aieva.config import get_settings

    get_settings(reload=True)

    worker = OcrWorker(pipeline=OcrPipeline(engines=[MockOcr(latex="x^2", plain="x**2")]))
    worker.submit(Image.new("RGB", (20, 20)))
    time.sleep(1.5)
    assert worker.stats.processed >= 1
    worker.stop()


def test_the_watcher_reads_a_folder(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    from aieva.config import get_settings

    get_settings(reload=True)

    inbox = tmp_path / "inbox"
    outbox = tmp_path / "outbox"
    inbox.mkdir()
    _image(inbox / "one.png")

    watcher = OcrWatcher(
        inbox, outbox, pipeline=OcrPipeline(engines=[MockOcr(latex="x^2", plain="x**2")])
    )
    results = watcher.run_once()
    assert len(results) == 1
    payload = json.loads((outbox / "one.json").read_text(encoding="utf-8"))
    assert payload["plain"] == "x**2"
    assert payload["source"].endswith("one.png")

    # the file is not read twice
    assert watcher.run_once() == []


def test_the_watcher_ignores_other_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    from aieva.config import get_settings

    get_settings(reload=True)

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "notes.txt").write_text("hello", encoding="utf-8")
    watcher = OcrWatcher(inbox, tmp_path / "outbox", pipeline=OcrPipeline(engines=[MockOcr()]))
    assert watcher.run_once() == []


def test_the_command_line_reads_the_inbox(tmp_path, capsys) -> None:
    inbox = tmp_path / "inbox"
    outbox = tmp_path / "outbox"
    inbox.mkdir()
    _image(inbox / "shot.png")
    code = main(["--inbox", str(inbox), "--outbox", str(outbox), "--mock", "--once"])
    assert code == 0
    assert "read 1 image(s)" in capsys.readouterr().out
    assert (outbox / "shot.json").exists()
