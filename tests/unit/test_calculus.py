"""Phase 5: the calculus visualisations."""

from __future__ import annotations

import math

import pytest
import sympy
from matplotlib.figure import Figure

from aieva.core.errors import SolveError
from aieva.plugins.math.calculus import (
    TangentSession,
    area_between,
    area_from_points,
    compute_integral,
    find_intersections,
    integral_view,
    polygon_area,
    riemann_sum,
    riemann_view,
    shape_area_view,
    simplify_polygon,
    stroke_to_points,
    tangent_view,
)

x = sympy.Symbol("x")


# ------------------------------------------------------------------- integrals
def test_integral_of_sin_from_zero_to_pi() -> None:
    result = compute_integral(sympy.sin(x), 0, math.pi)
    assert result.exact_value == pytest.approx(2.0, abs=1e-9)
    assert result.numeric == pytest.approx(2.0, abs=1e-9)
    assert result.warnings == []


def test_integral_of_x_squared_from_zero_to_one() -> None:
    result = compute_integral(x**2, 0, 1)
    assert result.exact_value == pytest.approx(1.0 / 3.0, abs=1e-12)
    assert result.numeric == pytest.approx(1.0 / 3.0, abs=1e-9)


def test_integral_view_produces_a_figure() -> None:
    import matplotlib.pyplot as plt

    result = integral_view(sympy.sin(x), 0, math.pi)
    try:
        assert isinstance(result.figure, Figure)
        assert result.meta["exact_value"] == pytest.approx(2.0, abs=1e-9)
        assert {spec.name for spec in result.parameters} == {"a", "b"}
    finally:
        plt.close(result.figure)


def test_integral_view_reports_a_mismatch() -> None:
    """A function SymPy cannot integrate exactly must warn instead of lying."""
    result = compute_integral(sympy.exp(-(x**2)) * sympy.sin(x), 0, 1)
    assert result.exact_value is None  # SymPy returns an unevaluated Integral
    assert result.numeric == pytest.approx(0.2946981822, abs=1e-6)
    assert any("numerical" in warning.lower() for warning in result.warnings)


# --------------------------------------------------------------- Riemann sums
def test_midpoint_riemann_sum_converges() -> None:
    total = riemann_sum(x**2, 0, 1, n=1000, method="midpoint")
    assert total == pytest.approx(1.0 / 3.0, abs=1e-4)


def test_all_riemann_methods_are_close() -> None:
    for method in ("left", "right", "midpoint", "trapezoid"):
        total = riemann_sum(sympy.sin(x), 0, math.pi, n=500, method=method)
        assert total == pytest.approx(2.0, abs=0.02)


def test_riemann_view_shows_sum_and_error() -> None:
    import matplotlib.pyplot as plt

    result = riemann_view(x**2, 0, 1, n=20, method="midpoint")
    try:
        assert isinstance(result.figure, Figure)
        assert result.meta["sum"] == pytest.approx(1.0 / 3.0, abs=0.01)
        assert result.meta["exact"] == pytest.approx(1.0 / 3.0, abs=1e-9)
        assert "error" in result.meta
    finally:
        plt.close(result.figure)


def test_riemann_view_rejects_unknown_method() -> None:
    with pytest.raises(SolveError):
        riemann_view(x**2, 0, 1, method="diagonal")


# --------------------------------------------------------------- tangent line
def test_tangent_view_and_session() -> None:
    import matplotlib.pyplot as plt

    result = tangent_view(sympy.sin(x), x0=0.0)
    try:
        assert isinstance(result.figure, Figure)
        assert result.meta["derivative"] == r"\cos{\left(x \right)}"
    finally:
        plt.close(result.figure)

    session = TangentSession(sympy.sin(x), x0=0.0)
    slope = session.set_x0(math.pi / 2)
    assert slope == pytest.approx(0.0, abs=1e-9)
    assert session.figure is not None
    plt.close(session.figure)


def test_tangent_session_steps() -> None:
    import matplotlib.pyplot as plt

    session = TangentSession(x**2, x0=0.0)
    new_x0 = session.step(0.5)
    assert new_x0 != 0.0
    assert session.x0 == pytest.approx(new_x0)
    plt.close(session.figure)


# ---------------------------------------------------------- area between curves
def test_area_between_x_and_x_squared() -> None:
    result = area_between(x, x**2, 0, 1)
    assert result.meta["area"] == pytest.approx(1.0 / 6.0, abs=1e-6)


def test_area_between_finds_intersections() -> None:
    roots = find_intersections(x, x**2, 0, 1)
    assert roots == pytest.approx([0.0, 1.0])


def test_area_between_with_explicit_bounds() -> None:
    import matplotlib.pyplot as plt

    result = area_between(x, x**2, 0, 1)
    try:
        assert isinstance(result.figure, Figure)
        assert result.meta["intersections"]
    finally:
        plt.close(result.figure)


# ------------------------------------------------------------------ shapes
def test_shoelace_area_of_a_unit_square() -> None:
    square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert polygon_area(square) == pytest.approx(1.0)


def test_area_from_points_trapezoid_and_simpson() -> None:
    xs = [0.0, 0.5, 1.0]
    ys = [0.0, 0.25, 1.0]
    # trapezoid: (0.5 * 0.25 / 2) + (0.5 * 1.25 / 2) = 0.375
    assert area_from_points(xs, ys, "trapz") == pytest.approx(0.375)
    # Simpson: h/3 * (y0 + 4*y1 + y2) = 0.5/3 * (0 + 1 + 1)
    assert area_from_points(xs, ys, "simpson") == pytest.approx(1.0 / 3.0)


def test_simplify_polygon_removes_redundant_points() -> None:
    points = [(0.0, 0.0), (1.0, 0.05), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    simplified = simplify_polygon(points, epsilon=1.0)
    assert len(simplified) < len(points)


def test_shape_area_view_uses_the_scale() -> None:
    import matplotlib.pyplot as plt

    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    result = shape_area_view(square, units_per_pixel=0.1)
    try:
        assert result.meta["area"] == pytest.approx(1.0)
        assert isinstance(result.figure, Figure)
    finally:
        plt.close(result.figure)


def test_stroke_to_points() -> None:
    points = stroke_to_points([0.0, 0.0, 1.0, 2.0, 3.0, 4.0])
    assert points == [(0.0, 0.0), (1.0, 2.0), (3.0, 4.0)]


def test_shape_area_needs_three_points() -> None:
    with pytest.raises(SolveError):
        shape_area_view([(0.0, 0.0), (1.0, 1.0)])


# ------------------------------------------------------------------- figures
@pytest.mark.parametrize(
    "builder",
    [
        lambda: integral_view(sympy.sin(x), 0, math.pi),
        lambda: riemann_view(sympy.sin(x), 0, math.pi, n=10),
        lambda: tangent_view(sympy.sin(x), 0.0),
        lambda: area_between(x, x**2, 0, 1),
        lambda: shape_area_view([(0, 0), (10, 0), (10, 10), (0, 10)]),
    ],
)
def test_figures_are_not_empty(builder) -> None:
    import matplotlib.pyplot as plt

    result = builder()
    figure = result.figure
    try:
        assert isinstance(figure, Figure)
        assert figure.axes
        assert len(figure.axes[0].lines) + len(figure.axes[0].patches) > 0
    finally:
        plt.close(figure)
