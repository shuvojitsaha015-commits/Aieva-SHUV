"""The life of a plot: who shows it, who closes it, who frees it.

A board computer draws plot after plot. Three things must be true:

* The old figure is **given back** - the memory of a whole lesson must
  not stay on the computer.
* The **other** figure keeps working. The old fix was
  ``plt.close("all")`` - that destroyed every plot that was on the
  screen. Now every figure has exactly one owner.
* Nothing is closed **twice** and nothing is closed **too early**.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module", autouse=True)
def _window():
    from kivy.core.window import Window  # noqa: F401

    return Window


@pytest.fixture
def session():
    from aieva.plugins.math.equations import PlotSession, analyze_equation

    plot_session = PlotSession(analyze_equation("y = m*x + c"))
    yield plot_session
    plot_session.close()


def test_the_modal_shows_the_figure(session) -> None:
    from aieva.ui.widgets.plot_modal import PlotModal

    modal = PlotModal(
        figure=session.figure,
        session=session,
        parameters=session.parameters,
        latex=session.info.latex,
    )
    try:
        modal.open()
        assert modal.figure is session.figure
        assert modal.canvas_widget is not None
        assert modal.canvas_widget.figure is session.figure
    finally:
        modal.dismiss()


def test_closing_the_modal_gives_the_memory_back(session) -> None:
    """The figure of the modal is released when the popup closes."""
    from aieva.core.plotting import FigureOwner
    from aieva.ui.widgets.plot_modal import PlotModal

    owner = FigureOwner(session.figure)
    modal = PlotModal(
        figure=session.figure,
        session=session,
        parameters=session.parameters,
        latex=session.info.latex,
        owner=owner,
    )
    modal.open()
    modal.dismiss()

    assert owner.released is True
    assert owner.figure is None


def test_closing_the_modal_twice_is_safe(session) -> None:
    from aieva.ui.widgets.plot_modal import PlotModal

    modal = PlotModal(figure=session.figure, session=session)
    modal.open()
    modal.dismiss()
    modal.dispose()  # must not raise


def test_replacing_a_plot_does_not_break_the_other_one() -> None:
    """The old bug: the second plot was destroyed with the first one."""
    from aieva.core.plotting import FigureOwner
    from aieva.plugins.math.equations import PlotSession, analyze_equation

    first = PlotSession(analyze_equation("y = x**2"))
    second = PlotSession(analyze_equation("y = x**3"))
    try:
        owner = FigureOwner(first.figure)
        owner.release()  # the first plot is replaced

        # the second plot still works
        assert second.figure.axes
        second.set_param("x", 2.0)
        assert second.figure.axes
        second.figure.savefig("/tmp/aieva-second-plot.png")
    finally:
        first.close()
        second.close()


def test_the_app_releases_the_plot_when_it_is_replaced() -> None:
    """``_release_plot`` gives the memory back - and only once."""
    from aieva.core.plotting import FigureOwner, new_subplots
    from aieva.ui.app import AievaApp

    class FakeApp:
        """Only the parts of the app that the release needs."""

        def __init__(self) -> None:
            self.plot_modal = None
            self._plot_owner = None
            self._plot_session = None
            self.dismissed = 0

        _release_plot = AievaApp._release_plot

        def _fake_dismiss(self) -> None:
            self.dismissed += 1

    app = FakeApp()
    figure, _axes = new_subplots()
    owner = FigureOwner(figure)
    app._plot_owner = owner

    class FakeModal:
        def __init__(self) -> None:
            self.disposed = 0

        def dismiss(self) -> None:
            app.dismissed += 1

        def dispose(self) -> None:
            self.disposed += 1

    modal = FakeModal()
    app.plot_modal = modal

    app._release_plot()

    assert owner.released is True
    assert modal.disposed == 1
    assert app.plot_modal is None
    assert app._plot_owner is None

    # a second call must not raise
    app._release_plot()


def test_the_app_closes_the_session_of_the_plot() -> None:
    """The session of the old plot is closed as well."""
    from aieva.ui.app import AievaApp

    class FakeSession:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    class FakeApp:
        def __init__(self) -> None:
            self.plot_modal = None
            self._plot_owner = None
            self._plot_session = None

        _release_plot = AievaApp._release_plot

    app = FakeApp()
    session = FakeSession()
    app._plot_session = session
    app._release_plot()
    assert session.closed == 1
