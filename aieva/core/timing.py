"""A tiny helper to log how long something takes.

The performance pass of Phase 12 wants the timings to be visible: every
slow part of Aieva logs its duration, so a slow board can be tuned (the
quality, the number of points, the cache).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

LOGGER = logging.getLogger("aieva.timing")


@contextmanager
def timed(name: str, logger: logging.Logger | None = None, level: int = logging.INFO) -> Iterator:
    """Log how long the block took (in milliseconds)."""
    log = logger or LOGGER
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000.0
        log.log(level, "%s took %.1f ms", name, elapsed)


def elapsed_ms(start: float) -> float:
    """The milliseconds since ``start`` (a ``time.perf_counter()`` value)."""
    return (time.perf_counter() - start) * 1000.0


__all__ = ["elapsed_ms", "timed"]
