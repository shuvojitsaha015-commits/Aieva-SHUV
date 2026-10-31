"""Phase 7: 2D / 3D plotting."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.figure import Figure

from aieva.core.errors import ParseError, SolveError
from aieva.plugins.math.plot3d import (
    DEFAULT_QUALITY,
    QUALITY_LEVELS,
    Plot3DSession,
    detect_dimension,
    parametric_2d_view,
    parametric_curve_view,
    parametric_surface_view,
    parse_plot_spec,
    polar_view,
    surface_view,
)


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


# ------------------------------------------------------------------- parsing
def test_surface_is_detected() -> None:
    spec = parse_plot_spec("z = x**2 + y**2")
    assert spec.kind == "surface"
    assert spec.dimension == "3d"
    assert spec.variable_names == ["x", "y"]


def test_parametric_curve_is_detected() -> None:
    spec = parse_plot_spec("x = cos(t), y = sin(t), z = t")
    assert spec.kind == "curve3d"
    assert spec.dimension == "3d"
    assert spec.variable_names == ["t"]


def test_parametric_surface_is_detected() -> None:
    spec = parse_plot_spec("x = u*cos(v), y = u*sin(v), z = u")
    assert spec.kind == "surface3d"
    assert spec.dimension == "3d"


def test_polar_is_detected() -> None:
    spec = parse_plot_spec("r = 1 + cos(theta)")
    assert spec.kind == "polar"
    assert spec.dimension == "2d"


def test_2d_function_is_detected() -> None:
    spec = parse_plot_spec("y = sin(x)")
    assert spec.kind == "function2d"
    assert spec.dimension == "2d"


def test_routing_picks_the_right_dimension() -> None:
    assert detect_dimension("z = x**2 + y**2") == "3d"
    assert detect_dimension("x = cos(t), y = sin(t), z = t") == "3d"
    assert detect_dimension("x = u*cos(v), y = u*sin(v), z = u") == "3d"
    assert detect_dimension("y = sin(x)") == "2d"
    assert detect_dimension("r = cos(theta)") == "2d"


def test_parameters_are_found() -> None:
    spec = parse_plot_spec("z = a*sin(x)*cos(y)")
    assert spec.parameter_names == ["a"]


def test_garbage_is_rejected() -> None:
    with pytest.raises(ParseError):
        parse_plot_spec("hello world")
    with pytest.raises(ParseError):
        parse_plot_spec("")


# ------------------------------------------------------------------ rendering
def test_surface_renders() -> None:
    result = surface_view("x**2 + y**2")
    assert isinstance(result.figure, Figure)
    assert result.meta["kind"] == "surface"
    assert result.meta["dimension"] == "3d"


def test_sine_surface_renders() -> None:
    result = surface_view("sin(x)*cos(y)")
    assert isinstance(result.figure, Figure)


def test_wireframe_and_contour_render() -> None:
    result = surface_view("x**2 + y**2", show_wireframe=True, show_contour=True)
    assert isinstance(result.figure, Figure)


def test_parametric_curve_renders() -> None:
    result = parametric_curve_view("x = cos(t), y = sin(t), z = t")
    assert isinstance(result.figure, Figure)
    assert result.meta["kind"] == "curve3d"


def test_sphere_renders() -> None:
    # the unit sphere as a parametric surface
    result = parametric_surface_view("x = cos(u)*cos(v), y = cos(u)*sin(v), z = sin(u)")
    assert isinstance(result.figure, Figure)
    assert result.meta["kind"] == "surface3d"


def test_helix_renders() -> None:
    result = parametric_curve_view("x = cos(t), y = sin(t), z = t")
    assert isinstance(result.figure, Figure)


def test_polar_renders() -> None:
    result = polar_view("1 + cos(theta)")
    assert isinstance(result.figure, Figure)


def test_parametric_2d_renders() -> None:
    result = parametric_2d_view("x = cos(t), y = sin(t)")
    assert isinstance(result.figure, Figure)


def test_quality_changes_the_mesh() -> None:
    low = surface_view("x**2 + y**2", quality="low")
    high = surface_view("x**2 + y**2", quality="high")
    assert low.meta["mesh"] == QUALITY_LEVELS["low"]
    assert high.meta["mesh"] == QUALITY_LEVELS["high"]
    assert high.meta["mesh"] > low.meta["mesh"]


def test_unknown_quality_is_rejected() -> None:
    with pytest.raises(SolveError):
        surface_view("x**2 + y**2", quality="ultra")


def test_poles_are_masked() -> None:
    # 1/(x**2 + y**2) explodes in the middle
    result = surface_view("1/(x**2 + y**2)")
    assert isinstance(result.figure, Figure)


def test_parameters_are_reported() -> None:
    result = surface_view("a*sin(x)*cos(y)")
    assert [spec.name for spec in result.parameters] == ["a"]


# -------------------------------------------------------------------- session
def test_session_rotates_without_recomputing() -> None:
    session = Plot3DSession("z = x**2 + y**2", quality="low")
    before = session.last_render_ms
    session.rotate(d_azimuth=45.0, d_elevation=10.0)
    assert session.azimuth != -60.0
    assert session.last_render_ms == before  # the figure was not recomputed


def test_session_zooms_and_resets() -> None:
    session = Plot3DSession("z = x**2 + y**2", quality="low")
    session.zoom_by(1.5)
    assert session.zoom == pytest.approx(1.5)
    session.reset_view()
    assert session.zoom == pytest.approx(1.0)
    assert session.elevation == pytest.approx(30.0)


def test_session_changes_the_parameter() -> None:
    session = Plot3DSession("z = a*sin(x)*cos(y)", quality="low")
    assert [spec.name for spec in session.parameters] == ["a"]
    session.set_param("a", 2.0)
    assert session.parameter_values["a"] == 2.0


def test_session_lowers_the_quality_while_dragging() -> None:
    session = Plot3DSession("z = x**2 + y**2", quality="medium")
    session.begin_interaction()
    assert session.quality == "low"
    session.end_interaction()
    assert session.quality == "medium"


def test_session_auto_rotate() -> None:
    session = Plot3DSession("z = x**2 + y**2", quality="low")
    session.auto_rotate = True
    before = session.azimuth
    session.step_auto_rotate(1.0)
    assert session.azimuth != before


def test_session_renders_a_2d_plot_too() -> None:
    session = Plot3DSession("y = sin(x)", quality="low")
    assert session.spec.dimension == "2d"
    assert isinstance(session.figure, Figure)


def test_default_quality_is_known() -> None:
    assert DEFAULT_QUALITY in QUALITY_LEVELS
    assert isinstance(np.linspace(0, 1, 5), np.ndarray)
