"""The figures must not pile up and must not invalidate each other.

Two mistakes are guarded against here.

**The pile.** ``matplotlib.pyplot`` remembers every figure it has ever
created. On a board computer the plots come one after the other - the
memory of the old figures is never given back, and Matplotlib starts to
complain ("More than 20 figures have been opened"). The figures of
Aieva are therefore built *directly*, without ``pyplot``.

**The wrong figure.** The old fix was ``plt.close("all")`` - and that
destroyed every figure that was on the screen, not only the one that
was replaced. Now every figure has exactly one owner, and the owner
gives back **its own** figure only.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from aieva.core.plotting import (
    FONT_NOT_FOUND,
    FigureOwner,
    close_figure,
    new_figure,
    new_subplots,
    quiet_matplotlib,
)


# --------------------------------------------------------------- the helpers
def test_a_new_figure_is_not_remembered_by_pyplot() -> None:
    """``pyplot`` must not keep the figure - that is the whole idea."""
    figure = new_figure()
    assert figure is not None
    assert plt.get_fignums() == []


def test_a_new_subplot_figure_is_not_remembered_by_pyplot() -> None:
    figure, axes = new_subplots()
    assert axes is not None
    assert plt.get_fignums() == []


def test_thirty_plots_do_not_pile_up() -> None:
    """A whole lesson of plots must not fill the list of Matplotlib."""
    for _ in range(30):
        figure, axes = new_subplots()
        axes.plot([0, 1], [0, 1])
    assert plt.get_fignums() == []


def test_the_figure_can_be_saved() -> None:
    """A direct figure works like every other figure."""
    figure, axes = new_subplots()
    axes.plot([0, 1], [0, 1])
    figure.savefig("/tmp/aieva-test-figure.png")
    assert figure.axes


# ---------------------------------------------------------------- the owner
def test_the_owner_gives_the_memory_back() -> None:
    owner = FigureOwner()
    figure, axes = new_subplots()
    axes.plot([0, 1], [0, 1])
    owner.adopt(figure)
    assert owner.figure is figure
    owner.release()
    assert owner.released is True
    assert owner.figure is None
    assert figure.axes == []


def test_the_owner_releases_only_once() -> None:
    owner = FigureOwner()
    figure, _axes = new_subplots()
    owner.adopt(figure)
    owner.release()
    owner.release()  # must not raise
    assert owner.released is True


def test_replacing_a_plot_does_not_invalidate_the_other_one() -> None:
    """The old bug: ``plt.close("all")`` destroyed the other plot."""
    first, first_axes = new_subplots()
    second, second_axes = new_subplots()
    first_axes.plot([0, 1], [0, 1])
    second_axes.plot([0, 1], [2, 3])

    owner = FigureOwner(first)
    owner.release()

    # the second figure still works
    assert second.axes
    second_axes.plot([2, 3], [4, 5])
    second.savefig("/tmp/aieva-test-second.png")
    assert len(second.axes) == 1


def test_two_owners_do_not_touch_each_other() -> None:
    first, _ = new_subplots()
    second, _ = new_subplots()
    owner_a = FigureOwner(first)
    owner_b = FigureOwner(second)
    owner_a.release()
    assert owner_b.figure is second
    assert second.axes


def test_adopt_releases_the_old_figure() -> None:
    owner = FigureOwner()
    first, _ = new_subplots()
    second, _ = new_subplots()
    owner.adopt(first)
    owner.adopt(second)
    assert first.axes == []
    assert owner.figure is second


def test_an_empty_owner_is_falsy() -> None:
    owner = FigureOwner()
    assert not owner
    figure, _ = new_subplots()
    owner.adopt(figure)
    assert owner


# ------------------------------------------------------------------- closing
def test_close_figure_only_touches_this_figure() -> None:
    first, _ = new_subplots()
    second, _ = new_subplots()
    close_figure(first)
    assert first.axes == []
    assert second.axes


def test_close_figure_tolerates_none() -> None:
    close_figure(None)  # must not raise


def test_close_figure_tolerates_a_broken_figure() -> None:
    class Broken:
        def clear(self) -> None:
            raise RuntimeError("boom")

    close_figure(Broken())  # must not raise


# --------------------------------------------------------------------- noise
def test_the_font_warning_is_only_written_once(caplog) -> None:
    """Hundreds of "font not found" lines must not drown the console."""
    import logging

    logger = logging.getLogger("matplotlib.font_manager")
    logger.setLevel(logging.WARNING)
    quiet_matplotlib()

    with caplog.at_level(logging.WARNING, logger="matplotlib.font_manager"):
        for _ in range(5):
            logger.warning("%s 'Segoe UI' not found.", FONT_NOT_FOUND)

    copies = [r for r in caplog.records if FONT_NOT_FOUND in r.getMessage()]
    assert len(copies) == 1


def test_other_warnings_stay_visible(caplog) -> None:
    """Only the *copies* of the font warning are dropped."""
    import logging

    logger = logging.getLogger("matplotlib.font_manager")
    logger.setLevel(logging.WARNING)
    quiet_matplotlib()

    with caplog.at_level(logging.WARNING, logger="matplotlib.font_manager"):
        logger.warning("a real warning about something else")

    assert any("a real warning" in r.getMessage() for r in caplog.records)
