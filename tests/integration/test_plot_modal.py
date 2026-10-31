"""Phase 4: the plot modal must work headless (Kivy + a virtual display)."""

from __future__ import annotations

import os

import numpy as np
import pytest

from aieva.core.models import ParamSpec
from aieva.plugins.math.equations import PlotSession, analyze_equation

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module", autouse=True)
def _window():
    """Create the Kivy window (needed by every widget)."""
    from kivy.core.window import Window  # noqa: F401

    return Window


@pytest.fixture
def session() -> PlotSession:
    plot_session = PlotSession(analyze_equation("y = m*x + c"))
    yield plot_session
    plot_session.close()


def test_plot_modal_opens_with_one_slider_per_parameter(session: PlotSession) -> None:
    from aieva.ui.widgets.plot_modal import PlotModal

    modal = PlotModal(
        figure=session.figure,
        session=session,
        parameters=session.parameters,
        latex=session.info.latex,
    )
    try:
        modal.open()
        assert modal.slider_panel is not None
        assert set(modal.slider_panel.rows) == {"m", "c"}
        row = modal.slider_panel.rows["m"]
        assert row.spec == ParamSpec(name="m", default=1.0, min=-10.0, max=10.0, step=0.1)
        assert row.slider.value == pytest.approx(1.0)
    finally:
        modal.dismiss()


def test_slider_change_updates_the_plot(session: PlotSession) -> None:
    from kivy.clock import Clock

    from aieva.ui.widgets.plot_modal import PlotModal

    modal = PlotModal(
        figure=session.figure,
        session=session,
        parameters=session.parameters,
        latex=session.info.latex,
    )
    try:
        modal.open()
        before = session.y_data().copy()
        row = modal.slider_panel.rows["m"]
        row.slider.value = 3.0
        # the update is throttled to ~30 Hz -> let the clock run
        for _ in range(5):
            Clock.tick()
        after = session.y_data()
        assert session.params["m"] == pytest.approx(3.0)
        assert after.size == before.size
        assert not np.array_equal(before, after, equal_nan=True)
    finally:
        modal.dismiss()


def test_reset_restores_the_defaults(session: PlotSession) -> None:
    from aieva.ui.widgets.plot_modal import PlotModal

    modal = PlotModal(
        figure=session.figure,
        session=session,
        parameters=session.parameters,
        latex=session.info.latex,
    )
    try:
        modal.open()
        modal.slider_panel.rows["m"].slider.value = 4.0
        modal._on_reset()
        assert session.params["m"] == pytest.approx(1.0)
        assert modal.slider_panel.rows["m"].slider.value == pytest.approx(1.0)
    finally:
        modal.dismiss()


def test_fine_tune_buttons_move_one_step(session: PlotSession) -> None:
    from aieva.ui.widgets.plot_modal import PlotModal

    modal = PlotModal(
        figure=session.figure,
        session=session,
        parameters=session.parameters,
        latex=session.info.latex,
    )
    try:
        modal.open()
        row = modal.slider_panel.rows["c"]
        start = row.value
        row.nudge(1)
        assert row.value == pytest.approx(start + row.spec.step)
        row.nudge(-1)
        assert row.value == pytest.approx(start)
    finally:
        modal.dismiss()


def test_input_bar_switches_between_text_and_latex() -> None:
    from aieva.ui.widgets.input_bar import InputBar

    bar = InputBar()
    received: list[tuple[str, str]] = []
    bar.on_submit = lambda text, kind: received.append((text, kind))
    bar.set_kind("latex")
    assert bar.kind == "latex"
    bar.set_text(r"x^{2} + y^{2} = r^{2}")
    bar._submit()
    assert received == [(r"x^{2} + y^{2} = r^{2}", "latex")]


def test_whiteboard_draws_and_exports() -> None:
    from aieva.ui.widgets.whiteboard import Whiteboard

    board = Whiteboard(size=(400, 300))
    board.pos = (0, 0)

    class FakeTouch:
        def __init__(self, x, y):
            self.x = x
            self.y = y
            self.pos = (x, y)
            self.ud: dict = {}

    board.on_touch_down(FakeTouch(10, 10))
    board.on_touch_move(FakeTouch(50, 40))
    board.on_touch_up(FakeTouch(50, 40))
    assert len(board.strokes) == 1

    image = board.export_to_image()
    assert image.size == (400, 300)
    assert image.mode == "RGBA"

    board.clear()
    assert board.strokes == []


def test_palm_rejection_ignores_large_contacts() -> None:
    from aieva.ui.widgets.whiteboard import Whiteboard

    board = Whiteboard(size=(400, 300))
    board.pos = (0, 0)
    board.palm_rejection = True
    board.palm_threshold = 50.0

    class PalmTouch:
        x = 10.0
        y = 10.0
        pos = (10.0, 10.0)
        major_radius = 120.0
        ud: dict = {}

    board.on_touch_down(PalmTouch())
    assert board.strokes == []


def test_history_roundtrip(tmp_path) -> None:
    from aieva.core.history import History

    history = History(path=tmp_path / "history.json")
    history.add("y = m*x + c", kind="text")
    history.add(r"x^{2} + y^{2} = r^{2}", kind="latex")
    entries = history.entries()
    assert len(entries) == 2
    assert entries[0].raw == r"x^{2} + y^{2} = r^{2}"
    history.clear()
    assert history.entries() == []


def test_display_is_available() -> None:
    assert os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")


def test_rapid_slider_moves_are_throttled(session: PlotSession) -> None:
    """A slider that is dragged fast must not flood the renderer."""
    from kivy.clock import Clock

    from aieva.ui.widgets.plot_modal import UPDATE_INTERVAL, PlotModal

    modal = PlotModal(
        figure=session.figure,
        session=session,
        parameters=session.parameters,
        latex=session.info.latex,
    )
    try:
        modal.open()
        calls: list[float] = []
        original = session.set_params

        def _counting(values):
            calls.append(float(session.params.get("m", 0.0)))
            return original(values)

        session.set_params = _counting  # type: ignore[method-assign]
        row = modal.slider_panel.rows["m"]
        for value in (1.1, 1.2, 1.3, 1.4, 1.5, 1.6):
            row.slider.value = value
        # the clock has not run yet -> nothing was drawn
        assert calls == []
        for _ in range(4):
            Clock.tick()
        # the moves were merged into one update
        assert len(calls) <= 2
        assert UPDATE_INTERVAL > 0
        assert session.params["m"] == pytest.approx(1.6)
    finally:
        modal.dismiss()
