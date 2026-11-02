"""When is the board worth reading again?

The service looks at the board again and again, but it must not read the
same picture over and over. :class:`TriggerPolicy` compares a small thumbnail
of the board with the last one and decides whether something was written.

The rules are simple:

* the board has to **change** (more than ``threshold`` of the pixels),
* at least ``min_interval`` seconds have to pass since the last reading,
* at most ``max_per_minute`` readings per minute (a safety belt).
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Sequence

from PIL import Image

#: The size of the thumbnail the comparison works on.
THUMBNAIL = (64, 64)


def fingerprint(image: Image.Image) -> tuple[int, ...]:
    """A small, comparable picture of the board."""
    grayscale = image.convert("L").resize(THUMBNAIL)
    return tuple(grayscale.getdata())


def difference(left: Sequence[int], right: Sequence[int]) -> float:
    """How much two thumbnails differ (0 = the same, 1 = completely different)."""
    if not left or len(left) != len(right):
        return 1.0
    total = sum(abs(int(a) - int(b)) for a, b in zip(left, right, strict=False))
    return total / (len(left) * 255.0)


class TriggerPolicy:
    """Decides when the board has changed enough to be read again."""

    def __init__(
        self,
        threshold: float = 0.004,
        min_interval: float = 2.0,
        max_per_minute: int = 12,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.threshold = max(0.0, float(threshold))
        self.min_interval = max(0.0, float(min_interval))
        self.max_per_minute = max(1, int(max_per_minute))
        self._clock = clock
        self._last_fingerprint: tuple[int, ...] | None = None
        self._last_run: float | None = None
        self._runs: deque[float] = deque()

    # ------------------------------------------------------------------ api
    def should_run(self, image: Image.Image, now: float | None = None) -> bool:
        """``True`` when the board should be read now."""
        moment = self._clock() if now is None else float(now)
        if self._last_run is not None and (moment - self._last_run) < self.min_interval:
            return False
        self._prune(moment)
        if len(self._runs) >= self.max_per_minute:
            return False
        current = fingerprint(image)
        if (
            self._last_fingerprint is not None
            and difference(current, self._last_fingerprint) < self.threshold
        ):
            return False
        self._last_fingerprint = current
        self._last_run = moment
        self._runs.append(moment)
        return True

    def remember(self, image: Image.Image) -> None:
        """Store the picture without reading it (used after an error)."""
        self._last_fingerprint = fingerprint(image)

    def reset(self) -> None:
        """Forget everything - the next picture is read again."""
        self._last_fingerprint = None
        self._last_run = None
        self._runs.clear()

    @property
    def runs(self) -> int:
        """How many readings happened in the last minute."""
        self._prune(self._clock())
        return len(self._runs)

    # ------------------------------------------------------------ internals
    def _prune(self, now: float) -> None:
        while self._runs and (now - self._runs[0]) > 60.0:
            self._runs.popleft()


__all__ = ["THUMBNAIL", "TriggerPolicy", "difference", "fingerprint"]
