"""Run slow work off the Kivy main thread.

The rule of the project: the UI thread never blocks. Every OCR call, LLM call
and heavy symbolic computation runs in a worker thread and the result is
delivered back on the main thread through :meth:`kivy.clock.Clock.schedule_once`.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from typing import Any

from kivy.clock import Clock


def run_in_background(
    work: Callable[[], Any],
    on_result: Callable[[Any], None] | None = None,
    on_error: Callable[[BaseException], None] | None = None,
    on_started: Callable[[], None] | None = None,
    name: str = "aieva-worker",
) -> threading.Thread:
    """Run ``work`` in a daemon thread and deliver the result on the UI thread.

    ``on_result`` / ``on_error`` are always called on the Kivy main thread.
    """

    def _worker() -> None:
        try:
            value = work()
        except BaseException as exc:  # noqa: BLE001 - forwarded to the UI
            traceback.print_exc()
            if on_error is not None:
                Clock.schedule_once(lambda _dt, error=exc: on_error(error), 0)
            return
        if on_result is not None:
            Clock.schedule_once(lambda _dt: on_result(value), 0)

    thread = threading.Thread(target=_worker, name=name, daemon=True)
    if on_started is not None:
        on_started()
    thread.start()
    return thread


__all__ = ["run_in_background"]
