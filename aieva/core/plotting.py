"""Figures that do not pile up and do not shout.

Three problems of Matplotlib are solved here.

**The pile of figures.** ``matplotlib.pyplot`` remembers every figure it
has ever created. A board computer draws plot after plot - and every
plot is a new figure - so the list grows until Matplotlib complains
("More than 20 figures have been opened") and the memory of the old
figures is never given back. The helpers below build the figures
*directly* (without ``pyplot``), so nothing is remembered and the old
figure is released as soon as the screen does not need it any more.

**Who may close a figure.** A figure belongs to exactly one owner.
:class:`FigureOwner` makes that visible: the owner gives the memory back
- and it gives back *this* figure only. A second plot that is on the
screen at the same time keeps working.

**The noise.** Matplotlib writes a line for every font it tries
(``findfont: score(...)``) - hundreds of lines for one plot. Kivy sets
the root logger to "everything", so those lines would be printed on the
console of the teacher. :func:`quiet_matplotlib` turns the debug noise
off; the real warnings and errors stay visible.

The module is Kivy-free (like the rest of :mod:`aieva.core`) and can be
used headless.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The loggers of Matplotlib that are far too talkative.
NOISY_LOGGERS = ("matplotlib", "matplotlib.font_manager")

#: The beginning of the message of a font that Matplotlib did not find.
FONT_NOT_FOUND = "findfont: Font family"


class _RepeatedFontWarning(logging.Filter):
    """Keeps the first "font not found" warning - drops the copies.

    Matplotlib writes ``findfont: Font family 'Segoe UI' not found.``
    once for **every** text of **every** plot - hundreds of lines that
    hide everything else on the console. The first line stays (the
    teacher learns that the font is missing), the copies are dropped.

    Nothing else is filtered: every other warning and every error of
    Matplotlib stays visible.
    """

    def __init__(self) -> None:
        super().__init__()
        self._seen: set[str] = set()

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if FONT_NOT_FOUND not in message:
            return True
        if message in self._seen:
            return False
        self._seen.add(message)
        return True


#: The filter that removes the copies of the "font not found" warning.
FONT_WARNING_FILTER = _RepeatedFontWarning()


def quiet_matplotlib() -> None:
    """Turn the debug noise of Matplotlib off.

    The real warnings and the errors stay - only the debug lines with
    the score of every font are gone. The copies of the "font family
    not found" warning are dropped as well (the first one stays).
    """
    for name in NOISY_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        if not any(isinstance(f, _RepeatedFontWarning) for f in logger.filters):
            logger.addFilter(FONT_WARNING_FILTER)


def new_figure(figsize: Any = None, dpi: Any = None) -> Any:
    """A Matplotlib figure that ``pyplot`` does not remember.

    The figure has its own Agg canvas, so ``savefig``, ``draw`` and
    ``draw_idle`` work exactly as with a normal figure.
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=figsize, dpi=dpi)
    FigureCanvasAgg(figure)
    return figure


def new_subplots(
    nrows: int = 1,
    ncols: int = 1,
    *,
    figsize: Any = None,
    dpi: Any = None,
    **kwargs: Any,
) -> tuple[Any, Any]:
    """Like ``plt.subplots`` - but the figure is not remembered.

    The return value is the same as the one of ``pyplot``: the figure
    and the axes (a single one, or a list of them).
    """
    figure = new_figure(figsize=figsize, dpi=dpi)
    axes = figure.subplots(nrows, ncols, **kwargs)
    return figure, axes


def close_figure(figure: Any) -> None:
    """Give the memory of a figure back.

    The figure is emptied and - when ``pyplot`` still knows it - closed.
    Every failure is ignored: closing a figure is a clean-up, it must
    never break the program.

    Only **this** figure is touched. Another figure that is shown at the
    same time keeps working - that is the whole point of the direct
    figures (see :func:`new_figure`).
    """
    if figure is None:
        return
    try:
        figure.clear()
    except Exception as exc:  # noqa: BLE001 - the clean-up is optional
        LOGGER.info("The figure could not be cleared: %s", exc)
    try:
        import matplotlib.pyplot as plt

        plt.close(figure)
    except Exception as exc:  # noqa: BLE001 - matplotlib may not be loaded
        LOGGER.info("The figure could not be closed: %s", exc)


class FigureOwner:
    """Owns one figure and gives its memory back - once.

    A figure that is shown on the screen belongs to somebody. The owner
    is that somebody: the screen that shows the picture calls
    :meth:`release` when the picture is not needed any more, and the
    memory goes back.

    The owner only ever touches **its own** figure. Replacing one plot
    therefore cannot invalidate another plot that is displayed at the
    same time - the old bug of ``plt.close("all")``.

    Examples
    --------
    >>> owner = FigureOwner()
    >>> owner.adopt(some_figure)
    >>> owner.release()          # the memory of ``some_figure`` goes back
    >>> owner.release()          # the second call does nothing
    """

    def __init__(self, figure: Any = None) -> None:
        self._figure = figure
        self._released = False

    @property
    def figure(self) -> Any:
        """The figure of the owner (``None`` after it was released)."""
        return None if self._released else self._figure

    @property
    def released(self) -> bool:
        """``True`` when the memory was already given back."""
        return self._released

    def adopt(self, figure: Any) -> None:
        """Take over a new figure - the old one is released first."""
        if figure is not self._figure:
            self.release()
        self._figure = figure
        self._released = False

    def release(self) -> None:
        """Give the memory of the figure back (only once)."""
        if self._released:
            return
        self._released = True
        figure, self._figure = self._figure, None
        close_figure(figure)

    def __bool__(self) -> bool:
        return not self._released and self._figure is not None


# The noise is turned off as soon as the module is used - every module
# that draws imports it.
quiet_matplotlib()


__all__ = [
    "FONT_NOT_FOUND",
    "FONT_WARNING_FILTER",
    "NOISY_LOGGERS",
    "FigureOwner",
    "close_figure",
    "new_figure",
    "new_subplots",
    "quiet_matplotlib",
]
