"""Tests for the dependency free numerical helpers (``core/numeric.py``)."""

from __future__ import annotations

import math
import sys

import pytest

from aieva.core import numeric


def test_adaptive_simpson_on_sin() -> None:
    value = numeric.adaptive_simpson(math.sin, 0.0, math.pi)
    assert value == pytest.approx(2.0, abs=1e-9)


def test_gauss_kronrod_on_sin() -> None:
    value, error = numeric.gauss_kronrod(math.sin, 0.0, math.pi)
    assert value == pytest.approx(2.0, abs=1e-9)
    assert error < 1e-8


def test_quad_uses_scipy_when_available() -> None:
    value, error = numeric.quad(math.sin, 0.0, math.pi)
    assert value == pytest.approx(2.0, abs=1e-9)
    assert error < 1e-8


def test_quad_falls_back_to_the_internal_implementation(monkeypatch: pytest.MonkeyPatch) -> None:
    """SciPy is optional - the internal quadrature must be used when it is gone."""
    monkeypatch.setitem(sys.modules, "scipy.integrate", None)
    value, _error = numeric.quad(math.sin, 0.0, math.pi)
    assert value == pytest.approx(2.0, abs=1e-8)


def test_quad_on_a_reversed_interval() -> None:
    value, _error = numeric.quad(math.sin, math.pi, 0.0)
    assert value == pytest.approx(-2.0, abs=1e-8)


def test_trapezoid_rule() -> None:
    assert numeric.trapezoid([0.0, 1.0, 2.0]) == pytest.approx(2.0)


def test_simpson_rule() -> None:
    assert numeric.simpson([0.0, 1.0, 2.0, 3.0, 4.0]) == pytest.approx(8.0)


def test_simpson_falls_back_to_trapezoid() -> None:
    assert numeric.simpson([0.0, 1.0]) == pytest.approx(0.5)


def test_brentq_finds_a_root() -> None:
    root = numeric.brentq(lambda t: t**2 - 2.0, 0.0, 2.0)
    assert root == pytest.approx(math.sqrt(2.0), abs=1e-10)


def test_brentq_requires_a_sign_change() -> None:
    with pytest.raises(ValueError):
        numeric.brentq(lambda t: t**2 + 1.0, 0.0, 2.0)


def test_ramer_douglas_peucker() -> None:
    points = [(0.0, 0.0), (1.0, 0.01), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    # a tolerance of 0.5 drops the nearly collinear point
    assert len(numeric.ramer_douglas_peucker(points, epsilon=0.5)) == 4
    # a tiny tolerance keeps every point
    assert len(numeric.ramer_douglas_peucker(points, epsilon=0.001)) == len(points)


def test_ramer_douglas_peucker_removes_collinear_points() -> None:
    points = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (2.0, 2.0)]
    simplified = numeric.ramer_douglas_peucker(points, epsilon=0.1)
    assert len(simplified) == 3


def test_polygon_area_of_a_unit_square() -> None:
    square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert numeric.polygon_area(square) == pytest.approx(1.0)


def test_polygon_area_needs_three_points() -> None:
    assert numeric.polygon_area([(0.0, 0.0), (1.0, 1.0)]) == 0.0


def test_polyline_area() -> None:
    assert numeric.polyline_area([(0.0, 0.0), (2.0, 2.0)]) == pytest.approx(2.0)


def test_scipy_availability_is_reported() -> None:
    assert isinstance(numeric.is_scipy_available(), bool)
