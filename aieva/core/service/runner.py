"""The background board service.

This is the application the instructor asked for: it runs **in the background
of the smart board**, notices what was written on the board, reads the
mathematics with the OCR, solves it and draws the graph - without anybody
having to touch the computer.

The service is pure Python (no Kivy), so it also runs on a small board
computer, it can be started automatically with the operating system and it
can be tested headlessly.

The result of a reading is written

* into the outbox (one JSON file per reading, plus a ``history.jsonl``),
* into the status file (:class:`~aieva.core.service.state.ServiceState`),
* into ``last_result.json`` - the file the floating window reads.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aieva.core.plotting import close_figure
from aieva.core.service.config import ServiceConfig, resolve
from aieva.core.service.scan import clear_request, read_region, read_request
from aieva.core.service.sources import NothingToCapture, build_source
from aieva.core.service.state import ServiceState, clear_stop_request, read_stop_request
from aieva.core.service.triggers import TriggerPolicy

LOGGER = logging.getLogger(__name__)

#: The name of the file the floating window reads.
RESULT_FILE_NAME = "last_result.json"

#: The callback that is told about a finished reading.
Notifier = Callable[[dict[str, Any]], None]


@dataclass
class ServiceRun:
    """What one cycle of the service did."""

    ran: bool = False
    reason: str = ""
    latex: str = ""
    plain: str = ""
    answer: str = ""
    answer_latex: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    #: The rectangle of the board that was read (pixels of the board).
    region: tuple[int, int, int, int] | None = None
    plot: str = ""
    capture: str = ""
    source: str = ""
    error: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """The run as a plain dictionary."""
        return {
            "ran": self.ran,
            "reason": self.reason,
            "latex": self.latex,
            "plain": self.plain,
            "answer": self.answer,
            "answer_latex": self.answer_latex,
            "steps": self.steps,
            "plot": self.plot,
            "region": list(self.region) if self.region else None,
            "capture": self.capture,
            "source": self.source,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
        }


class BackgroundService:
    """Watches the board and works on what it finds."""

    def __init__(
        self,
        config: ServiceConfig | None = None,
        source: Any = None,
        pipeline: Any = None,
        notifier: Notifier | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or ServiceConfig.from_env()
        self._source = source
        self._pipeline = pipeline
        self.notifier = notifier
        self._clock = clock
        self.trigger = TriggerPolicy(
            threshold=self.config.change_threshold,
            min_interval=self.config.min_interval_seconds,
            max_per_minute=self.config.max_runs_per_minute,
            clock=clock,
        )
        self.state = ServiceState()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------- the parts
    @property
    def source(self) -> Any:
        """The capture source (built on the first use)."""
        if self._source is None:
            self._source = build_source(self.config)
        return self._source

    @property
    def pipeline(self) -> Any:
        """The OCR pipeline (built on the first use)."""
        if self._pipeline is None:
            from aieva.core.ocr.pipeline import OcrPipeline

            if self.config.mock_ocr:
                from aieva.core.ocr.engines import MockOcr

                self._pipeline = OcrPipeline(engines=[MockOcr()])
            else:
                self._pipeline = OcrPipeline()
        return self._pipeline

    @property
    def is_running(self) -> bool:
        """``True`` while the service watches the board."""
        thread = self._thread
        return thread is not None and thread.is_alive()

    # --------------------------------------------------------------- the api
    def start(self) -> None:
        """Start the service in a background thread."""
        with self._lock:
            if self.is_running:
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self.run_forever, name="aieva-board-service", daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        """Ask the service to finish and wait for it."""
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    def run_forever(self) -> None:
        """The loop of the service - it runs until :meth:`stop` is called."""
        self.apply_environment()
        self.state.status = "running"
        self.state.started_at = self.state.started_at or time.time()
        self.state.pid = os.getpid()
        self.state.save(self.config.state_file)
        LOGGER.info("The background service watches the board every %s s", self.config.poll_seconds)
        while not self._stop.is_set():
            if read_stop_request(self.config.state_file):
                # the tray (or a script) asked the service to stop
                clear_stop_request(self.config.state_file)
                LOGGER.info("The service was asked to stop")
                break
            try:
                request = read_request(self.config.state_file)
                if request is not None:
                    clear_request(self.config.state_file)
                    run = self.scan_now(_region_of(request))
                    LOGGER.info("The board was read on request: %s", run.plain or run.latex)
                    self._stop.wait(self.config.poll_seconds)
                    continue
                run = self.run_once()
                if run.ran:
                    LOGGER.info("The board was read: %s", run.plain or run.latex)
            except Exception as exc:  # noqa: BLE001 - the service must survive
                self.state.errors += 1
                self.state.last_error = str(exc)
                self.state.status = "error"
                self.state.save(self.config.state_file)
                LOGGER.exception("The board could not be read")
            self._stop.wait(self.config.poll_seconds)
        self.state.status = "stopped"
        self.state.save(self.config.state_file)
        LOGGER.info("The background service has stopped")

    def run_once(self) -> ServiceRun:
        """One cycle: capture, decide, read, solve, publish."""
        started = time.perf_counter()
        source = self.source
        if source is None:
            raise RuntimeError("No capture source is available")
        try:
            capture = source.grab()
        except NothingToCapture as exc:
            return ServiceRun(ran=False, reason=str(exc))
        image = capture.image
        if not self.trigger.should_run(image, self._clock()):
            return ServiceRun(ran=False, reason="the board did not change")
        run = self._process(image, capture)
        run.duration_ms = (time.perf_counter() - started) * 1000.0
        return run

    def scan_now(self, region: tuple[int, int, int, int] | None = None) -> ServiceRun:
        """Read the board right now - the teacher tapped it.

        This is the *Google Lens* of the board: a tap, and the reading (with
        the solution and the graph) appears in the floating window.

        Without an area the whole board is read. But the area the teacher
        picked last is remembered - so the key (``F8``) and the button of
        the floating window read *that* part of the board again.
        """
        source = self.source
        if source is None:
            raise RuntimeError("No capture source is available")
        capture = source.grab()
        area = region or read_region(self.config.state_file)
        if area:
            capture = capture.crop(area)
        started = time.perf_counter()
        run = self._process(capture.image, capture, region=area)
        run.duration_ms = (time.perf_counter() - started) * 1000.0
        return run

    def status(self) -> dict[str, Any]:
        """What the service is doing right now."""
        return self.state.to_dict()

    def apply_environment(self) -> None:
        """Make the environment match the configuration (the OCR uses it)."""
        if self.config.server_url:
            os.environ["AIEVA_SERVER_URL"] = self.config.server_url
        if self.config.server_api_key:
            os.environ["AIEVA_SERVER_KEY"] = self.config.server_api_key

    # ------------------------------------------------------------ internals
    def _process(
        self,
        image: Any,
        capture: Any,
        region: tuple[int, int, int, int] | None = None,
    ) -> ServiceRun:
        """Read the picture and publish the result.

        ``region`` is the rectangle of the board that was read - it goes
        into the result, so the floating window can put the popup next to
        the writing.
        """
        capture_path = self._save_capture(image)
        try:
            result = self.pipeline.run(image)
        except Exception:
            # do not read the same broken picture over and over
            self.trigger.remember(image)
            raise
        text = (result.plain or result.latex or "").strip()
        intent = self._intent(result, text)
        answer = ""
        answer_latex = ""
        steps: list[dict[str, Any]] = []
        if self.config.auto_solve and text and intent.solve:
            answer, answer_latex, steps = self._solve(text)
        plot = ""
        if self.config.auto_plot and text and intent.graph:
            plot = self._draw(text)
        if not plot:
            # a table of values is a chart, not a function
            plot = self._draw_chart(getattr(result, "chart", None))
        payload = {
            "created_at": time.time(),
            "source": capture.source,
            "capture": str(capture_path) if capture_path else "",
            "latex": result.latex,
            "plain": result.plain,
            "confidence_note": result.confidence_note,
            "kind": result.kind,
            "engine": result.engine,
            "needs_manual_input": result.needs_manual_input,
            "intent": intent.to_dict(),
            "answer": answer,
            "answer_latex": answer_latex,
            "steps": steps,
            "plot": plot,
            "region": list(region) if region else None,
        }
        self._publish(payload)
        self._update_state(payload)
        if self.notifier is not None:
            try:
                self.notifier(payload)
            except Exception:  # noqa: BLE001 - a broken listener must not kill the service
                LOGGER.exception("The listener of the service failed")
        return ServiceRun(
            ran=True,
            reason="the board was read",
            latex=result.latex,
            plain=result.plain,
            answer=answer,
            answer_latex=answer_latex,
            steps=steps,
            plot=plot,
            region=region,
            capture=str(capture_path) if capture_path else "",
            source=capture.source,
        )

    def _intent(self, result: Any, text: str) -> Any:
        """What has to be done with the problem.

        Gemini decides (it read the board). When it did not say anything the
        local rules do it - the board must not stand still because the cloud
        had a bad day.
        """
        from aieva.core.service.intent import decide
        from aieva.plugins.math.classify import classify

        classification = classify(text) if text else None
        intent = decide(str(getattr(result, "intent", "") or ""), classification)
        if intent.source == "gemini":
            LOGGER.info("Gemini asks for: %s", intent.raw)
        return intent

    def _draw_chart(self, chart: Any) -> str:
        """Draw the chart of a table of values and return the file.

        The renderer is in the core, so every subject can use it - a table of
        speeds (physics) is drawn exactly like a table of marks (maths).
        """
        if not chart:
            return ""
        figure = None
        try:
            from aieva.core.charts import ChartData, chart_figure

            data = ChartData.from_dict(chart)
            if data.is_empty():
                return ""
            figure = chart_figure(data)
        except Exception as exc:  # noqa: BLE001 - the picture is a nice to have
            LOGGER.info("The chart could not be drawn: %s", exc)
            return ""
        try:
            directory = resolve(self.config.captures_dir).parent / "plots"
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"chart-{int(time.time() * 1000)}.png"
            figure.savefig(target, dpi=110, bbox_inches="tight")
            return str(target)
        except Exception as exc:  # noqa: BLE001 - the picture is a nice to have
            LOGGER.info("The chart could not be saved: %s", exc)
            return ""
        finally:
            self._close_figure(figure)

    def _save_capture(self, image: Any) -> Path | None:
        """Keep the picture of the board (for the history)."""
        try:
            directory = resolve(self.config.captures_dir)
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"board-{int(time.time() * 1000)}.png"
            image.save(target, format="PNG")
            return target
        except Exception as exc:  # noqa: BLE001 - the picture is a nice to have
            LOGGER.info("The picture of the board could not be saved: %s", exc)
            return None

    def _solve(self, text: str) -> tuple[str, str, list[dict[str, Any]]]:
        """Solve what was read (the SymPy answer wins)."""
        try:
            from aieva.plugins.math.classify import classify
            from aieva.plugins.math.solver import solve_expression

            classification = classify(text)
            outcome = solve_expression(text, classification=classification)
        except Exception as exc:  # noqa: BLE001 - the reading is still worth keeping
            LOGGER.info("What was read could not be solved: %s", exc)
            return "", "", []
        result = outcome.result
        steps = [step.to_dict() for step in result.steps]
        return result.answer_text, result.answer_latex, steps

    def _draw(self, text: str) -> str:
        """Draw the graph of what was read and return the file."""
        figure = None
        try:
            from aieva.core.models import ParsedInput
            from aieva.core.plugin_registry import get_plugin

            plugin = get_plugin("math")
            parsed = plugin.parse(ParsedInput(raw=text, kind="text", source="board"))
            session = plugin.create_session(parsed)
            figure = getattr(session, "figure", None)
            if figure is None:
                image_bytes = getattr(session, "image_bytes", None)
                if image_bytes:
                    return self._write_bytes(image_bytes)
        except Exception as exc:  # noqa: BLE001 - the picture is a nice to have
            LOGGER.info("What was read could not be drawn: %s", exc)
            return ""
        if figure is None:
            return ""
        try:
            directory = resolve(self.config.captures_dir).parent / "plots"
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"plot-{int(time.time() * 1000)}.png"
            figure.savefig(target, dpi=110, bbox_inches="tight")
            return str(target)
        except Exception as exc:  # noqa: BLE001 - the picture is a nice to have
            LOGGER.info("The graph could not be saved: %s", exc)
            return ""
        finally:
            self._close_figure(figure)

    def _write_bytes(self, image_bytes: bytes) -> str:
        directory = resolve(self.config.captures_dir).parent / "plots"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"plot-{int(time.time() * 1000)}.png"
        target.write_bytes(image_bytes)
        return str(target)

    @staticmethod
    def _close_figure(figure: Any) -> None:
        """Give the memory of the figure back (only this one)."""
        close_figure(figure)

    def _publish(self, payload: dict[str, Any]) -> Path:
        """Write the result (outbox, history and the file of the window)."""
        outbox = resolve(self.config.outbox)
        outbox.mkdir(parents=True, exist_ok=True)
        created = float(payload.get("created_at", time.time()))
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(created))
        target = outbox / f"board-{stamp}-{int(created * 1000) % 1000:03d}.json"
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        target.write_text(text, encoding="utf-8")

        history = outbox / "history.jsonl"
        with history.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._trim_history(history)

        result_file = result_path(self.config.state_file)
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text(text, encoding="utf-8")
        return target

    def _trim_history(self, history: Path) -> None:
        """Keep the history short."""
        keep = self.config.keep_history
        try:
            lines = history.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        if len(lines) <= keep:
            return
        try:
            history.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")
        except OSError as exc:
            LOGGER.info("The history could not be shortened: %s", exc)

    def _update_state(self, payload: dict[str, Any]) -> None:
        """Remember what happened in the status file."""
        self.state.runs += 1
        self.state.last_run_at = float(payload.get("created_at", time.time()))
        self.state.last_source = str(payload.get("source", ""))
        self.state.last_latex = str(payload.get("latex", ""))
        self.state.last_plain = str(payload.get("plain", ""))
        self.state.last_answer = str(payload.get("answer", ""))
        self.state.last_plot = str(payload.get("plot", ""))
        self.state.last_capture = str(payload.get("capture", ""))
        self.state.status = "running"
        self.state.save(self.config.state_file)


def result_path(state_file: str | Path) -> Path:
    """The file the service writes and the floating window reads."""
    return Path(state_file).with_name(RESULT_FILE_NAME)


def _region_of(request: dict[str, Any]) -> tuple[int, int, int, int] | None:
    """The area of the board the teacher tapped (if there is one)."""
    region = request.get("region")
    if not region or len(region) != 4:
        return None
    try:
        return tuple(int(value) for value in region)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


__all__ = ["RESULT_FILE_NAME", "BackgroundService", "Notifier", "ServiceRun", "result_path"]
