"""Phase 11: the settings screen and the plot canvas (headless)."""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module", autouse=True)
def _window():
    from kivy.core.window import Window  # noqa: F401

    return Window


@pytest.fixture(autouse=True)
def _restore_the_environment():
    """Saving the settings writes into the environment - restore it after."""
    import os

    from aieva.config import get_settings

    names = ("AIEVA_SERVER_URL", "AIEVA_QUALITY", "AIEVA_OFFLINE_MODE")
    old = {name: os.environ.get(name) for name in names}
    yield
    for name, value in old.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    get_settings(reload=True)


@pytest.fixture
def screen(tmp_path, monkeypatch):
    from aieva.ui.screens.settings import SettingsScreen

    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path))

    from aieva.config import get_settings

    get_settings(reload=True)
    widget = SettingsScreen()
    yield widget


def _wait_for(predicate, timeout: float = 15.0) -> bool:
    from kivy.clock import Clock

    deadline = time.time() + timeout
    while time.time() < deadline:
        Clock.tick()
        if predicate():
            return True
        time.sleep(0.02)
    return False


# ------------------------------------------------------------------- settings
def test_the_screen_shows_the_current_settings(screen) -> None:
    assert screen.quality_spinner.text in ("low", "normal", "high")
    assert screen.quality_spinner.text == "low"
    assert screen.pen_slider.value >= 1.0


def test_saving_writes_the_file(screen, tmp_path) -> None:
    screen.server_input.text = "http://10.0.0.5:8000"
    screen.quality_spinner.text = "high"
    screen.offline_switch.active = True
    screen.pen_slider.value = 9.0
    screen.save()
    assert "Saved" in screen.status_label.text
    assert (tmp_path / "user_settings.json").is_file()

    from aieva.core.user_settings import UserSettings

    stored = UserSettings.load(tmp_path / "user_settings.json")
    assert stored.server_url == "http://10.0.0.5:8000"
    assert stored.quality == "high"
    assert stored.offline_mode is True
    assert stored.pen_width == 9.0


def test_the_reset_shows_the_defaults(screen) -> None:
    screen.pen_slider.value = 12.0
    screen.quality_spinner.text = "low"
    screen.reset()
    assert screen.quality_spinner.text == "low"
    assert screen.pen_slider.value == 4.0


def test_the_whiteboard_follows_the_settings(screen) -> None:
    from aieva.ui.screens.whiteboard import WhiteboardScreen

    board = WhiteboardScreen()
    board.apply_settings(screen.current_settings())
    assert board.whiteboard.pen_width == screen.pen_slider.value
    assert board.whiteboard.palm_threshold == screen.palm_slider.value


# ---------------------------------------------------------------- plot canvas
def test_the_plot_canvas_shows_a_figure() -> None:
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    from aieva.ui.widgets.plot_canvas import PlotCanvas

    figure, axis = plt.subplots()
    axis.plot([0, 1], [0, 1])
    canvas = PlotCanvas(figure)
    assert canvas.figure is figure
    assert canvas.children
    canvas.draw_idle()
    plt.close(figure)


def test_the_png_fallback_renders_a_texture() -> None:
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    from aieva.ui.widgets.plot_canvas import PlotCanvas, figure_to_texture

    figure, axis = plt.subplots()
    axis.plot([0, 1], [1, 0])
    texture = figure_to_texture(figure)
    assert texture is not None
    assert texture.width > 10

    canvas = PlotCanvas(figure, backend="png")
    assert canvas.backend == "png"
    assert canvas.children
    canvas.draw_idle()
    plt.close(figure)


def test_the_backend_is_chosen_automatically() -> None:
    from aieva.ui.widgets.plot_canvas import select_backend

    assert select_backend() in ("kivyagg", "png")


def test_a_plot_canvas_without_a_figure_is_empty() -> None:
    from aieva.ui.widgets.plot_canvas import PlotCanvas

    canvas = PlotCanvas()
    assert canvas.figure is None
    assert not canvas.children
    canvas.draw_idle()


def test_the_computer_can_be_checked(screen) -> None:
    """The teacher asks whether this computer can read the board."""
    actions: list[str] = []
    screen.on_service_action = actions.append
    screen._service_action("check")
    assert actions == ["check"]
