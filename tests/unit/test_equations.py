"""Phase 3: equation analysis and the dynamic parameter plotting engine."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure

from aieva.core.errors import ParseError
from aieva.core.models import ParsedInput
from aieva.plugins.math.equations import (
    PlotSession,
    analyze_equation,
    build_evaluator,
    default_params,
    equation_specs,
    render,
    visualize_parsed,
)
from aieva.plugins.math.plugin import MathPlugin

CASES = equation_specs()


@pytest.fixture(autouse=True)
def _close_the_figures():
    """Every figure that a test leaves behind is closed."""
    import matplotlib.pyplot as plt

    yield
    plt.close("all")


@pytest.mark.parametrize("text,kind,parameters", CASES)
def test_analyze_equation_kind_and_parameters(text: str, kind: str, parameters: list[str]) -> None:
    info = analyze_equation(text)
    assert info.kind == kind
    assert info.parameter_names() == parameters


@pytest.mark.parametrize("text,kind,parameters", CASES)
def test_render_returns_a_figure(text: str, kind: str, parameters: list[str]) -> None:
    import matplotlib.pyplot as plt

    info = analyze_equation(text)
    figure = render(info)
    try:
        assert isinstance(figure, Figure)
        assert figure.axes
        assert figure.axes[0].get_title()
    finally:
        plt.close(figure)


@pytest.mark.parametrize("text,kind,parameters", CASES)
def test_plot_session_updates_the_data(text: str, kind: str, parameters: list[str]) -> None:
    info = analyze_equation(text)
    session = PlotSession(info)
    try:
        if info.kind == "explicit_y":
            before = session.y_data().copy()
            assert before.size > 0
            names = info.parameter_names()
            if names:
                session.set_param(names[0], 3.0)
                after = session.y_data()
                assert after.size == before.size
                assert not np.array_equal(before, after, equal_nan=True)
            else:
                # no parameter: the session must still redraw without errors
                assert session.set_params({}) >= 0.0
        else:
            assert session.figure is not None
            assert session.reset_params() >= 0.0
    finally:
        session.close()


def test_all_ten_equation_families_are_covered() -> None:
    assert len(CASES) >= 10


def test_default_params_values() -> None:
    info = analyze_equation("y = m*x + c")
    specs = {spec.name: spec for spec in default_params(info)}
    assert specs["m"].default == 1.0
    assert specs["m"].min == -10.0
    assert specs["m"].max == 10.0
    assert specs["m"].step == 0.1


def test_radius_parameter_has_its_own_range() -> None:
    info = analyze_equation("x**2 + y**2 = r**2")
    specs = {spec.name: spec for spec in default_params(info)}
    assert specs["r"].default == 5.0
    assert specs["r"].min == 0.1
    assert specs["r"].max == 20.0


def test_bare_expression_is_treated_as_y_equals() -> None:
    info = analyze_equation("sin(a*x)")
    assert info.kind == "explicit_y"
    assert info.parameter_names() == ["a"]
    assert info.independent == [__import__("sympy").Symbol("x")]


def test_implicit_circle_has_equal_aspect() -> None:
    import matplotlib.pyplot as plt

    info = analyze_equation("x**2 + y**2 = r**2")
    figure = render(info)
    try:
        assert figure.axes[0].get_aspect() == 1.0
    finally:
        plt.close(figure)


def test_circle_resizes_with_the_radius() -> None:
    session = PlotSession(analyze_equation("x**2 + y**2 = r**2"))
    try:
        before = session.axes.collections[0].get_paths()[0].vertices.copy()
        session.set_param("r", 7.0)
        after = session.axes.collections[0].get_paths()[0].vertices
        assert before.shape != after.shape or not np.array_equal(before, after)
    finally:
        session.close()


def test_asymptote_is_masked() -> None:
    session = PlotSession(analyze_equation("y = 1/x"))
    try:
        y_data = session.y_data()
        assert np.isnan(y_data).any()
        assert np.nanmax(np.abs(y_data)) < 1e6
    finally:
        session.close()


def test_logarithm_is_domain_masked() -> None:
    session = PlotSession(analyze_equation("y = log(x)"))
    try:
        y_data = session.y_data()
        assert np.isnan(y_data).any()
    finally:
        session.close()


def test_evaluator_uses_numpy() -> None:
    info = analyze_equation("y = m*x + c")
    evaluator = build_evaluator(info)
    values = evaluator.call(np.array([0.0, 1.0]), {"m": 2.0, "c": 1.0})
    assert np.allclose(values, [1.0, 3.0])


def test_parametric_and_polar() -> None:
    import sympy

    t = sympy.Symbol("t")
    info = analyze_equation((sympy.cos(t), sympy.sin(t)))
    assert info.kind == "parametric"
    assert render(info) is not None

    theta = sympy.Symbol("theta")
    polar = analyze_equation(sympy.Eq(sympy.Symbol("r"), 1 + sympy.cos(theta)))
    assert polar.kind == "polar"
    assert render(polar) is not None


def test_param_update_is_fast() -> None:
    """Soft target: a parameter update must stay below 80 ms for 1000 points.

    The real time is 28-40 ms; the limit is generous so that a slow machine
    (or the coverage instrumentation) does not fail the test.
    """
    session = PlotSession(analyze_equation("y = m*x + c"))
    try:
        session.set_param("m", 1.0)  # warm up (fonts, mathtext cache, ...)
        durations = [session.set_param("m", 1.0 + index * 0.1) for index in range(10)]
        average = sum(durations) / len(durations)
        median = sorted(durations)[len(durations) // 2]
        print(
            f"\n[benchmark] parameter update over ~1000 points: "
            f"average {average:.1f} ms, median {median:.1f} ms (soft target < 80 ms)"
        )
        assert average < 80.0
    finally:
        session.close()


def test_visualize_parsed_returns_parameters() -> None:
    plugin = MathPlugin()
    parsed = plugin.parse(ParsedInput(raw="y = m*x + c", kind="text"))
    result = plugin.visualize(parsed)
    try:
        assert {spec.name for spec in result.parameters} == {"m", "c"}
        assert result.figure is not None
        assert result.meta["kind"] == "explicit_y"
    finally:
        import matplotlib.pyplot as plt

        plt.close(result.figure)


def test_visualize_parsed_needs_a_parsed_input() -> None:
    with pytest.raises(ParseError):
        visualize_parsed(ParsedInput(raw="y = x"))
