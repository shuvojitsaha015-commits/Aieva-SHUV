"""The background OCR worker.

This is the piece the instructor asked for: an application that **runs in the
background and performs the OCR**. It is used in two ways:

* inside the Kivy app - :class:`OcrWorker` is a daemon thread with a queue, so
  a capture never blocks the UI thread;
* as a standalone service - ``python -m aieva.core.ocr.worker --inbox inbox``
  watches a folder, reads every new image in the background and writes the
  result as JSON into an outbox.

The worker never touches Kivy: it is pure Python and therefore testable
headlessly.
"""

from __future__ import annotations

import argparse
import json
import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from aieva.core.ocr.engines import OcrResult
from aieva.core.ocr.pipeline import OcrPipeline

LOGGER = logging.getLogger(__name__)

#: The file types the watcher picks up.
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")

#: The callback signature of a finished job.
OcrCallback = Callable[[OcrResult], None]


@dataclass
class OcrJob:
    """One capture waiting to be read."""

    image: Image.Image
    callback: OcrCallback | None = None
    identifier: str = ""


@dataclass
class OcrWorkerStats:
    """A snapshot of the worker."""

    processed: int = 0
    failed: int = 0
    pending: int = 0
    last_error: str = ""
    last_duration_ms: float = 0.0
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "processed": self.processed,
            "failed": self.failed,
            "pending": self.pending,
            "last_error": self.last_error,
            "last_duration_ms": round(self.last_duration_ms, 1),
            "uptime_seconds": round(time.time() - self.started_at, 1),
        }


class OcrWorker:
    """A background thread that reads images without blocking the caller."""

    def __init__(self, pipeline: OcrPipeline | None = None, name: str = "aieva-ocr") -> None:
        self.pipeline = pipeline or OcrPipeline()
        self.name = name
        self._queue: queue.Queue[OcrJob | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self.stats = OcrWorkerStats()

    # ------------------------------------------------------------------ api
    def start(self) -> None:
        """Start the background thread (idempotent)."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, name=self.name, daemon=True)
            self._thread.start()
            LOGGER.info("OCR worker %s started", self.name)

    def stop(self, timeout: float = 2.0) -> None:
        """Ask the thread to finish and wait for it."""
        with self._lock:
            self._running = False
            thread = self._thread
            self._thread = None
        self._queue.put(None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    def submit(
        self, image: Image.Image, callback: OcrCallback | None = None, identifier: str = ""
    ) -> None:
        """Queue an image. Returns immediately - the caller is never blocked."""
        self.start()
        self._queue.put(OcrJob(image=image, callback=callback, identifier=identifier))
        self.stats.pending = self._queue.qsize()

    def process_now(self, image: Image.Image) -> OcrResult:
        """Read an image in the calling thread (used by the tests)."""
        started = time.perf_counter()
        result = self.pipeline.run(image)
        self.stats.processed += 1
        self.stats.last_duration_ms = (time.perf_counter() - started) * 1000.0
        return result

    # ------------------------------------------------------------ internals
    def _loop(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                self._queue.task_done()
                break
            try:
                result = self.pipeline.run(job.image)
                self.stats.processed += 1
                if job.callback is not None:
                    try:
                        job.callback(result)
                    except Exception:  # noqa: BLE001 - a broken callback must not kill the worker
                        LOGGER.exception("The OCR callback failed")
            except Exception as exc:  # noqa: BLE001
                self.stats.failed += 1
                self.stats.last_error = str(exc)
                LOGGER.exception("The OCR job failed")
            finally:
                self.stats.pending = self._queue.qsize()
                self._queue.task_done()


class OcrWatcher:
    """A background service that reads every new image of a folder."""

    def __init__(
        self,
        inbox: str | Path,
        outbox: str | Path,
        pipeline: OcrPipeline | None = None,
        poll_seconds: float = 2.0,
        worker: OcrWorker | None = None,
    ) -> None:
        self.inbox = Path(inbox)
        self.outbox = Path(outbox)
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.outbox.mkdir(parents=True, exist_ok=True)
        self.poll_seconds = poll_seconds
        self.worker = worker or OcrWorker(pipeline=pipeline)
        self.seen: set[Path] = set()
        self._stop = threading.Event()

    # ------------------------------------------------------------------ api
    def pending_files(self) -> list[Path]:
        """The images that have not been read yet."""
        files = [
            path
            for path in sorted(self.inbox.iterdir())
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ]
        return [path for path in files if path not in self.seen]

    def process_file(self, path: Path) -> OcrResult:
        """Read one image and write the result into the outbox."""
        with Image.open(path) as image:
            loaded = image.convert("RGB")
            result = self.worker.process_now(loaded)
        payload = {"source": str(path), **result.to_dict()}
        target = self.outbox / f"{path.stem}.json"
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self.seen.add(path)
        LOGGER.info("OCR of %s finished (%s)", path.name, result.engine)
        return result

    def run_once(self) -> list[OcrResult]:
        """Read every pending image once. Returns the results."""
        results = []
        for path in self.pending_files():
            try:
                results.append(self.process_file(path))
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the service
                LOGGER.exception("Could not read %s: %s", path.name, exc)
                self.seen.add(path)
        return results

    def run_forever(self) -> None:
        """Poll the inbox until :meth:`stop` is called."""
        self.worker.start()
        LOGGER.info("Watching %s for new images", self.inbox)
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(self.poll_seconds)

    def stop(self) -> None:
        """Stop the watcher and the worker."""
        self._stop.set()
        self.worker.stop()


def build_parser() -> argparse.ArgumentParser:
    """The command line of the background OCR service."""
    parser = argparse.ArgumentParser(
        prog="aieva-ocr-worker",
        description="Aieva background OCR service: reads every new image of a folder.",
    )
    parser.add_argument("--inbox", default="ocr_inbox", help="the folder that is watched")
    parser.add_argument("--outbox", default="ocr_outbox", help="where the JSON results are written")
    parser.add_argument("--poll", type=float, default=2.0, help="the poll interval in seconds")
    parser.add_argument("--mock", action="store_true", help="use the mock OCR engine")
    parser.add_argument("--once", action="store_true", help="read the pending files and exit")
    parser.add_argument("--verbose", action="store_true", help="log every step")
    return parser


def main(argv: list[str] | None = None) -> int:
    """The entry point of the background OCR service."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    pipeline = None
    if args.mock:
        from aieva.core.ocr.engines import MockOcr

        pipeline = OcrPipeline(engines=[MockOcr()])
    watcher = OcrWatcher(args.inbox, args.outbox, pipeline=pipeline, poll_seconds=args.poll)
    if args.once:
        results = watcher.run_once()
        print(f"read {len(results)} image(s)")
        return 0
    try:
        watcher.run_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive
        pass
    finally:
        watcher.stop()
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())


__all__ = [
    "IMAGE_SUFFIXES",
    "OcrJob",
    "OcrWatcher",
    "OcrWorker",
    "OcrWorkerStats",
    "build_parser",
    "main",
]
