"""Calculus visualisations (feature 1.b).

Everything here is headless: the module produces Matplotlib figures and the
data the UI needs (exact value, numerical value, error, animation state). The
Kivy layer only animates what :class:`TangentSession` exposes.

Contents
--------
* :func:`integral_view` - definite integral with shaded area (exact + numeric).
* :func:`riemann_view` - Riemann sums (left / right / midpoint / trapezoid).
* :func:`tangent_view` / :class:`TangentSession` - moving tangent line.
* :func:`area_between` - area between two curves.
* :func:`area_from_points` / :func:`shape_area_view` - area of a drawn shape.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import sympy  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

from aieva.core import numeric  # noqa: E402
from aieva.core.errors import SolveError  # noqa: E402
from aieva.core.models import ParamSpec, VisualizationResult  # noqa: E402

RIEMANN_METHODS: tuple[str, ...] = ("left", "right", "midpoint", "trapezoid")

#: Colours used by the calculus views.
CURVE_COLOR = "#1f77b4"
POSITIVE_COLOR = "#2ca02c"
NEGATIVE_COLOR = "#d62728"
TANGENT_COLOR = "#ff7f0e"
RIEMANN_COLOR = "#9467bd"


# --------------------------------------------------------------------- helpers
def _as_expression(
    function: Any, symbol: sympy.Symbol | None = None
) -> tuple[sympy.Basic, sympy.Symbol]:
    """Return ``(expression, symbol)`` for a callable, a string or a SymPy object."""
    if isinstance(function, str):
        from aieva.core.safe_parse import parse_text_expression

        expression = parse_text_expression(function)
    elif isinstance(function, sympy.Basic):
        expression = function
    elif callable(function):
        raise SolveError("Calculus views need a symbolic expression, not a plain Python callable")
    else:
        raise SolveError(f"Cannot interpret {function!r} as an expression")

    free = sorted(expression.free_symbols, key=lambda item: item.name)
    if symbol is not None:
        return expression, symbol
    if not free:
        raise SolveError("The expression does not contain a variable")
    if len(free) > 1:
        raise SolveError(
            f"The expression has several variables ({', '.join(str(s) for s in free)}); "
            "only one is supported"
        )
    return expression, free[0]


def _numeric_function(expression: sympy.Basic, symbol: sympy.Symbol) -> Callable[[Any], Any]:
    """A NumPy callable for the expression."""
    return sympy.lambdify(symbol, expression, modules=["numpy"])


def _to_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _default_window(
    expression: sympy.Basic, symbol: sympy.Symbol, a: float | None, b: float | None
) -> tuple[float, float]:
    """A sensible x range for the plot."""
    if a is not None and b is not None:
        return float(min(a, b)), float(max(a, b))
    try:
        critical = sympy.solveset(expression, symbol, sympy.S.Reals)
        if isinstance(critical, sympy.FiniteSet):
            values = [float(item) for item in critical if item.is_real]
            if values:
                span = max(abs(min(values)), abs(max(values)), 1.0)
                return -span * 1.5, span * 1.5
    except Exception:  # noqa: BLE001 - the default window is best effort
        pass
    return -10.0, 10.0


# ------------------------------------------------------------------ integrals
@dataclass
class IntegralResult:
    """The outcome of a definite integral."""

    exact: sympy.Basic | None = None
    exact_value: float | None = None
    numeric: float = 0.0
    error: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def latex(self) -> str:
        if self.exact is not None:
            return sympy.latex(self.exact)
        return f"{self.numeric:.6g}"


def compute_integral(
    expression: Any,
    a: Any,
    b: Any,
    symbol: sympy.Symbol | None = None,
) -> IntegralResult:
    """Compute the exact and the numerical value of a definite integral."""
    expr, variable = _as_expression(expression, symbol)
    lower = _to_float(a)
    upper = _to_float(b)
    if lower is None or upper is None:
        raise SolveError("The integration bounds must be numbers")

    warnings: list[str] = []
    exact: sympy.Basic | None = None
    try:
        exact = sympy.integrate(expr, (variable, lower, upper))
    except Exception as exc:  # noqa: BLE001
        exact = None
        warnings.append(f"Symbolic integration failed: {exc}")

    exact_value: float | None = None
    if exact is not None and not isinstance(exact, sympy.Integral):
        exact_value = _to_float(sympy.N(exact))
    elif exact is not None:
        warnings.append("SymPy could not evaluate the integral exactly")

    func = _numeric_function(expr, variable)
    try:
        numeric_value, numeric_error = numeric.quad(func, lower, upper)
    except Exception as exc:  # noqa: BLE001
        raise SolveError(f"Numerical integration failed: {exc}") from exc

    if exact_value is None:
        warnings.append("Only a numerical value could be computed")
    elif abs(exact_value - numeric_value) > 1e-6:
        warnings.append(
            f"The symbolic value ({exact_value:.8g}) and the numerical value "
            f"({numeric_value:.8g}) differ by more than 1e-6"
        )

    return IntegralResult(
        exact=exact,
        exact_value=exact_value,
        numeric=float(numeric_value),
        error=float(numeric_error),
        warnings=warnings,
    )


def integral_view(
    expression: Any,
    a: Any,
    b: Any,
    symbol: sympy.Symbol | None = None,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Plot a definite integral and shade the area under the curve."""
    expr, variable = _as_expression(expression, symbol)
    lower = _to_float(a)
    upper = _to_float(b)
    if lower is None or upper is None:
        raise SolveError("The integration bounds must be numbers")

    result = compute_integral(expr, lower, upper, variable)
    func = _numeric_function(expr, variable)

    x_min, x_max = _default_window(expr, variable, lower, upper)
    x_values = np.linspace(x_min, x_max, 800)
    with np.errstate(all="ignore"):
        y_values = np.asarray(func(x_values), dtype=float)
    y_values = np.where(np.abs(y_values) > 1e9, np.nan, y_values)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.plot(x_values, y_values, color=CURVE_COLOR, linewidth=2.0, label="f(x)")
    ax.fill_between(
        x_values,
        0,
        y_values,
        where=y_values >= 0,
        color=POSITIVE_COLOR,
        alpha=0.35,
        interpolate=True,
    )
    ax.fill_between(
        x_values,
        0,
        y_values,
        where=y_values <= 0,
        color=NEGATIVE_COLOR,
        alpha=0.35,
        interpolate=True,
    )
    ax.axvline(lower, color="0.3", linestyle="--", linewidth=1.2)
    ax.axvline(upper, color="0.3", linestyle="--", linewidth=1.2)
    ax.axhline(0, color="0.35", linewidth=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("$x$")
    ax.set_ylabel("$f(x)$")
    ax.set_title(rf"$\int_{{{lower:g}}}^{{{upper:g}}} {sympy.latex(expr)}\,dx$")
    annotation = (
        f"exact = {result.latex}"
        if result.exact_value is not None
        else f"numeric = {result.numeric:.6g}"
    )
    if result.exact_value is not None:
        annotation += f"\nnumeric = {result.numeric:.6g}"
    ax.text(
        0.03,
        0.97,
        annotation,
        transform=ax.transAxes,
        fontsize=10,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
    )
    fig.tight_layout()

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(
                name="a",
                default=float(lower),
                min=float(lower) - 10,
                max=float(upper) + 10,
                step=0.1,
            ),
            ParamSpec(
                name="b",
                default=float(upper),
                min=float(lower) - 10,
                max=float(upper) + 10,
                step=0.1,
            ),
        ],
        meta={
            "kind": "integral",
            "exact": str(result.exact) if result.exact is not None else None,
            "exact_value": result.exact_value,
            "numeric": result.numeric,
            "error": result.error,
            "warnings": result.warnings,
            "latex": result.latex,
            "bounds": [float(lower), float(upper)],
            "variable": str(variable),
        },
    )


# --------------------------------------------------------------- Riemann sums
def riemann_sum(
    expression: Any,
    a: float,
    b: float,
    n: int = 20,
    method: str = "left",
    symbol: sympy.Symbol | None = None,
) -> float:
    """The value of a Riemann sum of ``expression`` on ``[a, b]``."""
    if method not in RIEMANN_METHODS:
        raise SolveError(f"Unknown Riemann method {method!r} (use one of {RIEMANN_METHODS})")
    expr, variable = _as_expression(expression, symbol)
    func = _numeric_function(expr, variable)
    n = max(int(n), 1)
    width = (b - a) / n
    edges = np.linspace(a, b, n + 1)

    if method == "left":
        samples = edges[:-1]
    elif method == "right":
        samples = edges[1:]
    elif method == "midpoint":
        samples = 0.5 * (edges[:-1] + edges[1:])
    else:  # trapezoid
        samples = edges

    with np.errstate(all="ignore"):
        values = np.asarray(func(samples), dtype=float)
    values = np.where(np.abs(values) > 1e12, 0.0, values)

    if method == "trapezoid":
        left = np.asarray(func(edges[:-1]), dtype=float)
        right = np.asarray(func(edges[1:]), dtype=float)
        left = np.where(np.abs(left) > 1e12, 0.0, left)
        right = np.where(np.abs(right) > 1e12, 0.0, right)
        return float(np.sum((left + right) / 2.0 * width))
    return float(np.sum(values) * width)


def riemann_view(
    expression: Any,
    a: float,
    b: float,
    n: int = 20,
    method: str = "left",
    symbol: sympy.Symbol | None = None,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw the Riemann rectangles / trapezoids of a function."""
    if method not in RIEMANN_METHODS:
        raise SolveError(f"Unknown Riemann method {method!r} (use one of {RIEMANN_METHODS})")
    expr, variable = _as_expression(expression, symbol)
    func = _numeric_function(expr, variable)

    n = max(int(n), 1)
    lower = float(a)
    upper = float(b)
    width = (upper - lower) / n
    edges = np.linspace(lower, upper, n + 1)

    total = riemann_sum(expr, lower, upper, n, method, variable)
    exact = compute_integral(expr, lower, upper, variable)
    exact_value = exact.exact_value if exact.exact_value is not None else exact.numeric
    error = total - exact_value

    x_min, x_max = _default_window(expr, variable, lower, upper)
    x_values = np.linspace(x_min, x_max, 800)
    with np.errstate(all="ignore"):
        y_values = np.asarray(func(x_values), dtype=float)
    y_values = np.where(np.abs(y_values) > 1e9, np.nan, y_values)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.plot(x_values, y_values, color=CURVE_COLOR, linewidth=2.0, label="f(x)")

    with np.errstate(all="ignore"):
        if method == "trapezoid":
            left_values = np.asarray(func(edges[:-1]), dtype=float)
            right_values = np.asarray(func(edges[1:]), dtype=float)
            for index in range(n):
                polygon = Polygon(
                    [
                        (edges[index], 0.0),
                        (edges[index + 1], 0.0),
                        (edges[index + 1], right_values[index]),
                        (edges[index], left_values[index]),
                    ],
                    closed=True,
                    facecolor=RIEMANN_COLOR,
                    edgecolor="#5b3f8c",
                    alpha=0.45,
                )
                ax.add_patch(polygon)
        else:
            if method == "left":
                samples = edges[:-1]
            elif method == "right":
                samples = edges[1:]
            else:
                samples = 0.5 * (edges[:-1] + edges[1:])
            heights = np.asarray(func(samples), dtype=float)
            heights = np.where(np.abs(heights) > 1e12, 0.0, heights)
            for index in range(n):
                height = heights[index]
                ax.add_patch(
                    Rectangle(
                        (edges[index], min(0.0, height)),
                        width,
                        abs(height),
                        facecolor=RIEMANN_COLOR,
                        edgecolor="#5b3f8c",
                        alpha=0.45,
                    )
                )

    ax.axhline(0, color="0.35", linewidth=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("$x$")
    ax.set_ylabel("$f(x)$")
    ax.set_title(rf"{sympy.latex(expr)} - {method} sum, n = {n}")
    ax.text(
        0.03,
        0.97,
        f"sum = {total:.8g}\nexact = {exact_value:.8g}\nerror = {error:.3g}",
        transform=ax.transAxes,
        fontsize=10,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
    )
    fig.tight_layout()

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name="n", default=float(n), min=1, max=200, step=1),
            ParamSpec(name="a", default=lower, min=lower - 10, max=upper + 10, step=0.1),
            ParamSpec(name="b", default=upper, min=lower - 10, max=upper + 10, step=0.1),
        ],
        meta={
            "kind": "riemann",
            "method": method,
            "n": n,
            "sum": total,
            "exact": exact_value,
            "error": error,
            "warnings": exact.warnings,
            "latex": sympy.latex(expr),
            "bounds": [lower, upper],
        },
    )


# ------------------------------------------------------------- tangent line
class TangentSession:
    """A moving tangent line.

    The UI animates it with ``Clock.schedule_interval`` and calls
    :meth:`step`; the maths stays completely outside Kivy.
    """

    def __init__(
        self,
        expression: Any,
        x0: float = 0.0,
        symbol: sympy.Symbol | None = None,
        figsize: tuple[float, float] = (7.0, 5.0),
        dpi: int = 100,
    ) -> None:
        self.expression, self.variable = _as_expression(expression, symbol)
        self.derivative = sympy.diff(self.expression, self.variable)
        self.func = _numeric_function(self.expression, self.variable)
        self.deriv_func = _numeric_function(self.derivative, self.variable)
        self.x0 = float(x0)
        self.speed = 1.0
        self._build(figsize, dpi)

    # ------------------------------------------------------------------ UI
    def _build(self, figsize: tuple[float, float], dpi: int) -> None:
        self.figure, self.ax = plt.subplots(figsize=figsize, dpi=dpi)
        x_min, x_max = _default_window(self.expression, self.variable, None, None)
        self.x_values = np.linspace(x_min, x_max, 800)
        with np.errstate(all="ignore"):
            self.y_values = np.asarray(self.func(self.x_values), dtype=float)
        self.y_values = np.where(np.abs(self.y_values) > 1e9, np.nan, self.y_values)
        (self.curve,) = self.ax.plot(
            self.x_values, self.y_values, color=CURVE_COLOR, linewidth=2.0, label="f(x)"
        )
        (self.tangent_line,) = self.ax.plot(
            [], [], color=TANGENT_COLOR, linewidth=2.0, label="tangent"
        )
        (self.point,) = self.ax.plot([], [], "o", color=TANGENT_COLOR, markersize=8)
        self.slope_text = self.ax.text(
            0.03,
            0.97,
            "",
            transform=self.ax.transAxes,
            fontsize=10,
            va="top",
            ha="left",
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
        )
        self.ax.axhline(0, color="0.35", linewidth=0.9)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlabel("$x$")
        self.ax.set_ylabel("$f(x)$")
        self.ax.set_title(rf"tangent to {sympy.latex(self.expression)}")
        self.set_x0(self.x0)
        self.figure.tight_layout()

    # ----------------------------------------------------------------- API
    def set_x0(self, x0: float) -> float:
        """Move the tangent point to ``x0`` and redraw."""
        self.x0 = float(x0)
        value = float(self.func(self.x0))
        slope = float(self.deriv_func(self.x0))
        span = float(self.x_values[-1] - self.x_values[0])
        line_x = np.linspace(self.x0 - span / 2.0, self.x0 + span / 2.0, 50)
        line_y = slope * (line_x - self.x0) + value
        self.tangent_line.set_data(line_x, line_y)
        self.point.set_data([self.x0], [value])
        self.slope_text.set_text(
            f"x0 = {self.x0:.3f}\nf' = {sympy.latex(self.derivative)}\n"
            f"slope = {slope:.4g}\nf(x0) = {value:.4g}"
        )
        self.figure.canvas.draw_idle()
        return slope

    def step(self, dt: float) -> float:
        """Advance the animation by ``dt`` seconds and return the new ``x0``."""
        span = float(self.x_values[-1] - self.x_values[0])
        new_x0 = self.x0 + self.speed * dt * span / 4.0
        if new_x0 > self.x_values[-1]:
            new_x0 = self.x_values[0]
        if new_x0 < self.x_values[0]:
            new_x0 = self.x_values[-1]
        self.set_x0(new_x0)
        return new_x0


def tangent_view(
    expression: Any,
    x0: float = 0.0,
    symbol: sympy.Symbol | None = None,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw a function and its tangent line at ``x0``."""
    session = TangentSession(expression, x0, symbol, figsize, dpi)
    return VisualizationResult(
        figure=session.figure,
        parameters=[
            ParamSpec(name="x0", default=float(x0), min=-10.0, max=10.0, step=0.05),
        ],
        meta={
            "kind": "tangent",
            "derivative": sympy.latex(session.derivative),
            "derivative_sympy": str(session.derivative),
            "antiderivative": sympy.latex(sympy.integrate(session.expression, session.variable)),
            "latex": sympy.latex(session.expression),
            "x0": float(x0),
        },
    )


# -------------------------------------------------------- area between curves
def find_intersections(
    f: Any,
    g: Any,
    a: float | None = None,
    b: float | None = None,
    symbol: sympy.Symbol | None = None,
) -> list[float]:
    """The real intersection points of two curves (sorted)."""
    expr_f, variable = _as_expression(f, symbol)
    expr_g, _ = _as_expression(g, variable)
    difference = sympy.simplify(expr_f - expr_g)

    roots: list[float] = []
    try:
        solutions = sympy.solve(difference, variable)
    except Exception:  # noqa: BLE001
        solutions = []
    for solution in solutions or []:
        if solution.free_symbols:
            continue
        value = _to_float(solution)
        if value is None:
            continue
        if a is not None and value < a - 1e-9:
            continue
        if b is not None and value > b + 1e-9:
            continue
        roots.append(value)

    if not roots:
        roots = _numeric_intersections(expr_f, expr_g, variable, a, b)

    return sorted({round(value, 10) for value in roots})


def _numeric_intersections(
    expr_f: sympy.Basic,
    expr_g: sympy.Basic,
    variable: sympy.Symbol,
    a: float | None,
    b: float | None,
) -> list[float]:
    """Scan for sign changes and refine them with Brent's method."""
    func_f = _numeric_function(expr_f, variable)
    func_g = _numeric_function(expr_g, variable)
    difference = lambda point: float(func_f(point)) - float(func_g(point))  # noqa: E731

    left = a if a is not None else -10.0
    right = b if b is not None else 10.0
    samples = np.linspace(left, right, 400)
    roots: list[float] = []
    previous_x = float(samples[0])
    previous_value = difference(previous_x)
    for sample in samples[1:]:
        current_x = float(sample)
        current_value = difference(current_x)
        if previous_value == 0.0:
            roots.append(previous_x)
        elif previous_value * current_value < 0:
            try:
                roots.append(numeric.brentq(difference, previous_x, current_x))
            except Exception:  # noqa: BLE001
                pass
        previous_x, previous_value = current_x, current_value
    return roots


def area_between(
    f: Any,
    g: Any,
    a: float | None = None,
    b: float | None = None,
    symbol: sympy.Symbol | None = None,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Compute and shade the area between two curves."""
    expr_f, variable = _as_expression(f, symbol)
    expr_g, _ = _as_expression(g, variable)

    intersections = find_intersections(expr_f, expr_g, a, b, variable)
    if a is None or b is None:
        if len(intersections) >= 2:
            lower, upper = intersections[0], intersections[-1]
        elif intersections:
            lower, upper = intersections[0] - 5.0, intersections[0] + 5.0
        else:
            lower, upper = -5.0, 5.0
    else:
        lower, upper = float(a), float(b)

    bounds = [lower] + [value for value in intersections if lower < value < upper] + [upper]

    total = 0.0
    pieces: list[tuple[float, float, float]] = []
    difference = sympy.lambdify(variable, sympy.Abs(expr_f - expr_g), modules=["numpy"])

    def _height(point: float) -> float:
        return float(difference(point))

    for index in range(len(bounds) - 1):
        left, right = bounds[index], bounds[index + 1]
        if right - left <= 0:
            continue
        with np.errstate(all="ignore"):
            area, _error = numeric.quad(_height, left, right)
        total += abs(area)
        pieces.append((left, right, abs(area)))

    func_f = _numeric_function(expr_f, variable)
    func_g = _numeric_function(expr_g, variable)
    x_min, x_max = _default_window(expr_f, variable, lower, upper)
    x_values = np.linspace(x_min, x_max, 800)
    with np.errstate(all="ignore"):
        y_f = np.asarray(func_f(x_values), dtype=float)
        y_g = np.asarray(func_g(x_values), dtype=float)
    y_f = np.where(np.abs(y_f) > 1e9, np.nan, y_f)
    y_g = np.where(np.abs(y_g) > 1e9, np.nan, y_g)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.plot(x_values, y_f, color=CURVE_COLOR, linewidth=2.0, label="f(x)")
    ax.plot(x_values, y_g, color="#ff7f0e", linewidth=2.0, label="g(x)")
    ax.fill_between(x_values, y_f, y_g, color=RIEMANN_COLOR, alpha=0.35)
    for point in intersections:
        ax.axvline(point, color="0.45", linestyle=":", linewidth=1.0)
    ax.axhline(0, color="0.35", linewidth=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("$x$")
    ax.set_ylabel("y")
    ax.set_title("area between curves")
    ax.text(
        0.03,
        0.97,
        f"area = {total:.8g}\nintersections = "
        + (", ".join(f"{value:.4g}" for value in intersections) or "none"),
        transform=ax.transAxes,
        fontsize=10,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
    )
    fig.tight_layout()

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(
                name="a", default=float(lower), min=float(lower) - 5, max=float(upper) + 5, step=0.1
            ),
            ParamSpec(
                name="b", default=float(upper), min=float(lower) - 5, max=float(upper) + 5, step=0.1
            ),
        ],
        meta={
            "kind": "area_between",
            "area": total,
            "intersections": intersections,
            "pieces": pieces,
            "bounds": [float(lower), float(upper)],
            "latex": f"{sympy.latex(expr_f)} - {sympy.latex(expr_g)}",
            "warnings": [],
        },
    )


# --------------------------------------------------------- areas of shapes
def area_from_points(
    xs: Sequence[float],
    ys: Sequence[float],
    method: str = "trapz",
) -> float:
    """The area under a sampled curve (or of a closed polygon).

    ``method`` is ``"trapz"`` (trapezoid rule), ``"simpson"`` or
    ``"polygon"`` (shoelace formula for a closed shape).
    """
    if len(xs) != len(ys):
        raise SolveError("x and y must have the same length")
    if len(xs) < 2:
        return 0.0
    if method == "trapz":
        return float(numeric.trapezoid(ys, xs))
    if method == "simpson":
        return float(numeric.simpson(ys, xs))
    if method == "polygon":
        return float(numeric.polygon_area(list(zip(xs, ys, strict=False))))
    raise SolveError(f"Unknown area method {method!r}")


def polygon_area(points: Sequence[tuple[float, float]]) -> float:
    """The area of a closed polygon (shoelace formula)."""
    return float(numeric.polygon_area(list(points)))


def simplify_polygon(
    points: Sequence[tuple[float, float]], epsilon: float = 2.0
) -> list[tuple[float, float]]:
    """Simplify a drawn polyline (Ramer-Douglas-Peucker)."""
    return numeric.ramer_douglas_peucker(list(points), epsilon)


def shape_area_view(
    points: Sequence[tuple[float, float]],
    units_per_pixel: float = 1.0,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw a shape (for example a whiteboard stroke) and annotate its area.

    ``units_per_pixel`` is the calibration: how many math units one pixel
    represents.
    """
    if len(points) < 3:
        raise SolveError("A shape needs at least three points")

    scaled = [(x * units_per_pixel, y * units_per_pixel) for x, y in points]
    area = polygon_area(scaled)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    xs = [point[0] for point in scaled]
    ys = [point[1] for point in scaled]
    ax.fill(xs, ys, color=RIEMANN_COLOR, alpha=0.35, edgecolor="#5b3f8c")
    ax.plot(xs + [xs[0]], ys + [ys[0]], color="#5b3f8c", linewidth=2.0)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("area of the drawn shape")
    ax.text(
        0.03,
        0.97,
        f"area = {area:.8g} units²\n({len(points)} points, " f"1 px = {units_per_pixel:g} units)",
        transform=ax.transAxes,
        fontsize=10,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
    )
    fig.tight_layout()

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name="scale", default=float(units_per_pixel), min=0.01, max=10.0, step=0.01),
        ],
        meta={
            "kind": "shape_area",
            "area": area,
            "points": [list(point) for point in scaled],
            "units_per_pixel": float(units_per_pixel),
            "warnings": [],
        },
    )


def stroke_to_points(stroke_points: Sequence[float]) -> list[tuple[float, float]]:
    """Convert a flat ``[x0, y0, x1, y1, ...]`` stroke into points."""
    values = list(stroke_points)
    return [(values[index], values[index + 1]) for index in range(0, len(values) - 1, 2)]


__all__ = [
    "RIEMANN_METHODS",
    "IntegralResult",
    "TangentSession",
    "area_between",
    "area_from_points",
    "compute_integral",
    "find_intersections",
    "integral_view",
    "polygon_area",
    "riemann_sum",
    "riemann_view",
    "shape_area_view",
    "simplify_polygon",
    "stroke_to_points",
    "tangent_view",
]
