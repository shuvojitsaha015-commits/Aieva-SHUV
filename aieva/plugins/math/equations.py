"""Equation analysis and dynamic parameter plotting (feature 1.a).

Everything in this module is headless: it produces Matplotlib figures but never
touches Kivy. The UI (Phase 4) only calls :func:`visualize_parsed` and drives a
:class:`PlotSession`.

Supported equation kinds:

``explicit_y``
    ``y = m*x + c`` - plotted as a line, parameters are the free symbols.
``implicit``
    ``x**2 + y**2 = r**2`` - plotted as a zero level contour.
``parametric``
    ``(x(t), y(t))`` - a tuple of two expressions.
``polar``
    ``r = 1 + cos(theta)`` - plotted on a polar axis.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import sympy  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from aieva.core.errors import ParseError, VisualizationError  # noqa: E402
from aieva.core.models import ParamSpec, ParsedInput, VisualizationResult  # noqa: E402
from aieva.core.safe_parse import parse_equation, parse_text_expression  # noqa: E402

#: Symbols that are treated as the plot variables of an implicit curve.
IMPLICIT_AXES: tuple[str, ...] = ("x", "y")

#: Parameters that behave like a radius: positive, larger default.
RADIUS_NAMES: frozenset[str] = frozenset({"r", "R", "radius", "rad"})

#: Values larger than this are treated as a discontinuity (asymptote).
ASYMPTOTE_LIMIT = 1e6

#: Number of sample points along the x axis (odd -> a symmetric window hits 0).
GRID_POINTS = 1001

DEFAULT_WINDOW: tuple[float, float, float, float] = (-10.0, 10.0, -10.0, 10.0)

LOGGER = logging.getLogger(__name__)


# --------------------------------------------------------------------- models
@dataclass
class EquationInfo:
    """Everything the plot engine needs to know about an equation."""

    kind: str
    expression: sympy.Basic
    lhs: sympy.Basic | None = None
    rhs: sympy.Basic | None = None
    dependent: str = "y"
    independent: list[sympy.Symbol] = field(default_factory=list)
    parameters: list[sympy.Symbol] = field(default_factory=list)
    latex: str = ""
    raw: str = ""
    parametric_exprs: tuple[sympy.Basic, sympy.Basic] | None = None

    @property
    def is_implicit(self) -> bool:
        return self.kind == "implicit"

    @property
    def variables(self) -> list[str]:
        """The names of the independent variables."""
        return [str(symbol) for symbol in self.independent]

    def variable_names(self) -> list[str]:
        """The names of the independent variables."""
        return self.variables

    def parameter_names(self) -> list[str]:
        return [str(symbol) for symbol in self.parameters]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "expression": sympy.srepr(self.expression),
            "dependent": self.dependent,
            "independent": self.variable_names,
            "parameters": self.parameter_names(),
            "latex": self.latex,
            "raw": self.raw,
        }


@dataclass
class Evaluator:
    """A lambdified function plus the order of its arguments."""

    kind: str
    func: Callable[..., Any]
    variables: list[sympy.Symbol]
    parameters: list[sympy.Symbol]

    def parameter_defaults(self) -> dict[str, float]:
        return {str(symbol): 1.0 for symbol in self.parameters}

    def call(self, grid: Any, params: Mapping[str, float]) -> np.ndarray:
        """Evaluate the expression for ``grid`` using ``params``."""
        values = [float(params.get(str(symbol), 1.0)) for symbol in self.parameters]
        with np.errstate(all="ignore"):
            if self.kind == "implicit":
                x_grid, y_grid = grid
                return np.asarray(self.func(x_grid, y_grid, *values), dtype=float)
            if self.kind == "parametric":
                t_grid = grid
                x_values, y_values = self.func(t_grid, *values)
                return np.asarray(x_values, dtype=float), np.asarray(y_values, dtype=float)
            return np.asarray(self.func(grid, *values), dtype=float)


# ------------------------------------------------------------------ analysis
def _normalize_input(expr_or_eq: Any) -> tuple[sympy.Basic | None, sympy.Basic, str]:
    """Return ``(lhs, rhs, raw_text)`` for anything the user may have given."""
    raw = ""
    if isinstance(expr_or_eq, str):
        raw = expr_or_eq
        text = expr_or_eq.strip()
        if "=" in text:
            equation = parse_equation(text)
            return equation.lhs, equation.rhs, raw
        return None, parse_text_expression(text), raw
    if isinstance(expr_or_eq, sympy.Equality):
        return expr_or_eq.lhs, expr_or_eq.rhs, raw
    if isinstance(expr_or_eq, sympy.Basic):
        return None, expr_or_eq, raw
    raise ParseError(f"Cannot analyse {expr_or_eq!r}")


def _as_parametric(expr_or_eq: Any) -> tuple[sympy.Basic, sympy.Basic] | None:
    """Recognise ``(x(t), y(t))`` given as a tuple / list of two expressions."""
    if isinstance(expr_or_eq, (tuple, list)) and len(expr_or_eq) == 2:
        first, second = expr_or_eq
        if isinstance(first, sympy.Basic) and isinstance(second, sympy.Basic):
            return first, second
    if isinstance(expr_or_eq, sympy.Tuple) and len(expr_or_eq) == 2:
        return expr_or_eq[0], expr_or_eq[1]
    return None


def analyze_equation(expr_or_eq: Any) -> EquationInfo:
    """Work out the kind of an equation, its variables and its parameters.

    Examples
    --------
    >>> info = analyze_equation("y = m*x + c")
    >>> info.kind, info.parameter_names()
    ('explicit_y', ['c', 'm'])
    """
    parametric = _as_parametric(expr_or_eq)
    if parametric is not None:
        return _analyze_parametric(parametric, expr_or_eq)

    lhs, rhs, raw = _normalize_input(expr_or_eq)

    if lhs is None:
        expression = rhs
        dependent = "y"
    elif isinstance(lhs, sympy.core.function.AppliedUndef):
        # f(x) = ...  -> treat the right hand side as the function
        expression = rhs
        dependent = lhs.func.__name__
    elif isinstance(lhs, sympy.Symbol) and lhs.name != "x":
        # y = ...  (or any other single symbol on the left)
        expression = rhs
        dependent = lhs.name
    else:
        # x = ..., or a general expression such as x**2 + y**2 = r**2
        expression = sympy.expand(lhs - rhs) if lhs is not None else rhs
        dependent = "y"

    free = set(expression.free_symbols)
    axes = [sympy.Symbol(name) for name in IMPLICIT_AXES if sympy.Symbol(name) in free]

    if len(axes) == 2:
        kind = "implicit"
        independent = axes
        parameters = sorted(free - set(axes), key=lambda s: s.name)
        dependent = "y"
    else:
        if sympy.Symbol("x") in free:
            independent = [sympy.Symbol("x")]
        elif len(free) == 1:
            independent = [next(iter(free))]
        else:
            independent = [sympy.Symbol("x")]
        kind = "polar" if sympy.Symbol("theta") in free else "explicit_y"
        parameters = sorted(free - set(independent), key=lambda s: s.name)
        if dependent == "x" and sympy.Symbol("x") in parameters:
            parameters.remove(sympy.Symbol("x"))

    latex = _equation_latex(lhs, rhs)
    return EquationInfo(
        kind=kind,
        expression=expression,
        lhs=lhs,
        rhs=rhs,
        dependent=dependent,
        independent=independent,
        parameters=parameters,
        latex=latex,
        raw=raw,
    )


def _analyze_parametric(pair: tuple[sympy.Basic, sympy.Basic], original: Any) -> EquationInfo:
    x_expr, y_expr = pair
    combined = x_expr + y_expr
    free = set(combined.free_symbols)
    t_symbol = sympy.Symbol("t")
    if t_symbol in free:
        independent = [t_symbol]
    else:
        candidates = sorted(free - set(), key=lambda s: s.name)
        independent = [candidates[0]] if candidates else [t_symbol]
    parameters = sorted(free - set(independent), key=lambda s: s.name)
    latex = rf"\left({sympy.latex(x_expr)},\,{sympy.latex(y_expr)}\right)"
    return EquationInfo(
        kind="parametric",
        expression=combined,
        lhs=None,
        rhs=None,
        dependent="y",
        independent=independent,
        parameters=parameters,
        latex=latex,
        raw=str(original),
        parametric_exprs=(x_expr, y_expr),
    )


def _equation_latex(lhs: sympy.Basic | None, rhs: sympy.Basic) -> str:
    if lhs is None:
        return sympy.latex(rhs)
    return f"{sympy.latex(lhs)} = {sympy.latex(rhs)}"


# ------------------------------------------------------------------- sliders
def default_params(info: EquationInfo) -> list[ParamSpec]:
    """One :class:`ParamSpec` per free parameter of the equation."""
    specs: list[ParamSpec] = []
    for symbol in info.parameters:
        name = str(symbol)
        if name in RADIUS_NAMES:
            specs.append(ParamSpec(name=name, default=5.0, min=0.1, max=20.0, step=0.1))
        else:
            specs.append(ParamSpec(name=name, default=1.0, min=-10.0, max=10.0, step=0.1))
    return specs


# ----------------------------------------------------------------- evaluators
def build_evaluator(info: EquationInfo) -> Evaluator:
    """Create a NumPy callable for the equation."""
    variables = list(info.independent)
    parameters = list(info.parameters)

    try:
        if info.kind == "implicit":
            args = (variables[0], variables[1], *parameters)
            func = sympy.lambdify(args, info.expression, modules=["numpy"])
        elif info.kind == "parametric":
            assert info.parametric_exprs is not None
            x_expr, y_expr = info.parametric_exprs
            args = (variables[0], *parameters)
            func = sympy.lambdify(args, (x_expr, y_expr), modules=["numpy"])
        else:
            args = (variables[0], *parameters)
            func = sympy.lambdify(args, info.expression, modules=["numpy"])
    except Exception as exc:  # noqa: BLE001
        raise VisualizationError(f"Could not build a numerical evaluator: {exc}") from exc

    return Evaluator(kind=info.kind, func=func, variables=variables, parameters=parameters)


# -------------------------------------------------------------------- render
def _is_circle(info: EquationInfo) -> bool:
    """True for ``x**2 + y**2 = r**2`` style curves (equal aspect looks right)."""
    if info.kind != "implicit":
        return False
    x_symbol, y_symbol = info.independent[0], info.independent[1]
    try:
        poly = sympy.Poly(info.expression, x_symbol, y_symbol)
    except Exception:  # noqa: BLE001 - not a polynomial
        return False
    try:
        terms = dict(zip(poly.monoms(), poly.coeffs(), strict=False))
    except Exception:  # noqa: BLE001
        return False
    x2 = terms.get((2, 0), sympy.Integer(0))
    y2 = terms.get((0, 2), sympy.Integer(0))
    if x2 == 0 or y2 == 0:
        return False
    if sympy.simplify(x2 - y2) != 0:
        return False
    for (power_x, power_y), _coefficient in terms.items():
        if power_x == 0 and power_y == 0:
            continue  # the constant term (for example -r**2)
        if power_x + power_y == 1:  # a linear term would make it an ellipse
            return False
        if power_x == 1 and power_y == 1:  # a rotated ellipse
            return False
    return True


def mask_discontinuities(y_values: np.ndarray) -> np.ndarray:
    """Break the line at asymptotes so that no vertical connector is drawn."""
    y_values = np.asarray(y_values, dtype=float)
    finite = np.isfinite(y_values)
    if finite.sum() < 3:
        return y_values
    differences = np.abs(np.diff(y_values))
    finite_differences = differences[np.isfinite(differences)]
    if finite_differences.size == 0:
        return y_values
    threshold = max(1e3 * float(np.median(finite_differences)), 1e6)
    breaks = np.where(differences > threshold)[0]
    if breaks.size:
        y_values = y_values.copy()
        y_values[breaks] = np.nan
        y_values[breaks + 1] = np.nan
    return y_values


def _style_axes(ax: Any, info: EquationInfo, window: tuple[float, float, float, float]) -> None:
    x_min, x_max, y_min, y_max = window
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.grid(True, alpha=0.3, linewidth=0.6)
    ax.axhline(0.0, color="0.35", linewidth=0.9)
    ax.axvline(0.0, color="0.35", linewidth=0.9)
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    if info.kind == "implicit":
        ax.set_xlabel("$x$")
        ax.set_ylabel("$y$")
    if _is_circle(info):
        ax.set_aspect("equal", adjustable="box")


#: ``gid`` of the text artist that shows the live parameter values.
VALUES_GID = "aieva-parameter-values"


def _static_title(info: EquationInfo) -> str:
    """The (static) mathtext title of the figure."""
    return f"${info.latex}$"


def _values_label(params: Mapping[str, float]) -> str:
    """A plain text summary of the current parameter values (cheap to update)."""
    if not params:
        return ""
    return ",  ".join(f"{name} = {value:g}" for name, value in sorted(params.items()))


def _update_values_label(ax: Any, params: Mapping[str, float]) -> None:
    """Refresh the parameter readout without re-rendering any mathtext."""
    label = _values_label(params)
    for artist in ax.texts:
        if artist.get_gid() == VALUES_GID:
            artist.set_text(label)
            return
    ax.text(
        0.02,
        0.96,
        label,
        transform=ax.transAxes,
        fontsize=9,
        va="top",
        ha="left",
        gid=VALUES_GID,
        bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
    )


def render(
    info: EquationInfo,
    param_values: Mapping[str, float] | None = None,
    view_window: tuple[float, float, float, float] = DEFAULT_WINDOW,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> Figure:
    """Render the equation and return the Matplotlib figure."""
    params = {spec.name: spec.default for spec in default_params(info)}
    if param_values:
        params.update({str(k): float(v) for k, v in param_values.items()})

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    evaluator = build_evaluator(info)
    x_min, x_max, y_min, y_max = view_window

    try:
        if info.kind == "implicit":
            x_values = np.linspace(x_min, x_max, 400)
            y_values = np.linspace(y_min, y_max, 400)
            x_grid, y_grid = np.meshgrid(x_values, y_values)
            field = evaluator.call((x_grid, y_grid), params)
            field = np.where(np.abs(field) > ASYMPTOTE_LIMIT, np.nan, field)
            ax.contour(x_grid, y_grid, field, levels=[0.0], colors="#1f77b4", linewidths=2.0)
        elif info.kind == "parametric":
            t_values = np.linspace(-2 * np.pi, 2 * np.pi, 800)
            x_values, y_values = evaluator.call(t_values, params)
            ax.plot(x_values, y_values, color="#1f77b4", linewidth=2.0)
        elif info.kind == "polar":
            theta_values = np.linspace(0, 2 * np.pi, 800)
            radius = evaluator.call(theta_values, params)
            ax.plot(theta_values, radius, color="#1f77b4", linewidth=2.0)
            ax.set_xlabel(r"$\theta$")
            ax.set_ylabel(r"$r$")
        else:
            x_values = np.linspace(x_min, x_max, GRID_POINTS)
            y_values = evaluator.call(x_values, params)
            y_values = np.where(np.abs(y_values) > ASYMPTOTE_LIMIT, np.nan, y_values)
            y_values = mask_discontinuities(y_values)
            ax.plot(x_values, y_values, color="#1f77b4", linewidth=2.0)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        plt.close(fig)
        raise VisualizationError(f"Could not plot the equation: {exc}") from exc

    _style_axes(ax, info, view_window)
    ax.set_title(_static_title(info), fontsize=12)
    _update_values_label(ax, params)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------- update
def update(
    fig: Figure,
    info: EquationInfo,
    new_params: Mapping[str, float],
    view_window: tuple[float, float, float, float] = DEFAULT_WINDOW,
    evaluator: Evaluator | None = None,
) -> Figure:
    """Update an existing figure with new parameter values.

    Passing a cached ``evaluator`` avoids re-running ``sympy.lambdify`` and
    keeps the update well below one frame (important for the sliders).
    """
    params = {spec.name: spec.default for spec in default_params(info)}
    params.update({str(k): float(v) for k, v in new_params.items()})
    ax = fig.axes[0] if fig.axes else fig.add_subplot(111)
    if evaluator is None:
        evaluator = build_evaluator(info)
    x_min, x_max, y_min, y_max = view_window

    if info.kind == "implicit":
        x_values = np.linspace(x_min, x_max, 400)
        y_values = np.linspace(y_min, y_max, 400)
        x_grid, y_grid = np.meshgrid(x_values, y_values)
        field = evaluator.call((x_grid, y_grid), params)
        field = np.where(np.abs(field) > ASYMPTOTE_LIMIT, np.nan, field)
        for collection in list(ax.collections):
            collection.remove()
        ax.contour(x_grid, y_grid, field, levels=[0.0], colors="#1f77b4", linewidths=2.0)
    elif info.kind == "parametric":
        t_values = np.linspace(-2 * np.pi, 2 * np.pi, 800)
        x_values, y_values = evaluator.call(t_values, params)
        if ax.lines:
            ax.lines[0].set_data(x_values, y_values)
        else:
            ax.plot(x_values, y_values, color="#1f77b4", linewidth=2.0)
    elif info.kind == "polar":
        theta_values = np.linspace(0, 2 * np.pi, 800)
        radius = evaluator.call(theta_values, params)
        if ax.lines:
            ax.lines[0].set_data(theta_values, radius)
        else:
            ax.plot(theta_values, radius, color="#1f77b4", linewidth=2.0)
    else:
        x_values = np.linspace(x_min, x_max, GRID_POINTS)
        y_values = evaluator.call(x_values, params)
        y_values = np.where(np.abs(y_values) > ASYMPTOTE_LIMIT, np.nan, y_values)
        y_values = mask_discontinuities(y_values)
        if ax.lines:
            ax.lines[0].set_ydata(y_values)
        else:
            ax.plot(x_values, y_values, color="#1f77b4", linewidth=2.0)

    _update_values_label(ax, params)
    fig.canvas.draw_idle()
    return fig


class PlotSession:
    """Holds the figure, the axes and the artists so the UI can move sliders.

    ``session.set_param("m", 2.0)`` re-evaluates the equation and redraws.
    """

    def __init__(
        self,
        info: EquationInfo,
        param_values: Mapping[str, float] | None = None,
        view_window: tuple[float, float, float, float] = DEFAULT_WINDOW,
        figsize: tuple[float, float] = (7.0, 5.0),
        dpi: int = 100,
    ) -> None:
        self.info = info
        self.view_window = view_window
        self.params: dict[str, float] = {spec.name: spec.default for spec in default_params(info)}
        if param_values:
            self.params.update({str(k): float(v) for k, v in param_values.items()})
        self.evaluator = build_evaluator(info)
        self.parameters = default_params(info)
        self.figure = render(info, self.params, view_window, figsize, dpi)
        self.axes = self.figure.axes[0]
        self.last_update_ms: float = 0.0

    # ------------------------------------------------------------------ API
    def set_param(self, name: str, value: float) -> float:
        """Set one parameter and redraw. Returns the duration in milliseconds."""
        start = time.perf_counter()
        self.params[str(name)] = float(value)
        update(self.figure, self.info, self.params, self.view_window, self.evaluator)
        self.last_update_ms = (time.perf_counter() - start) * 1000.0
        LOGGER.info("the plot of %s was updated in %.1f ms", name, self.last_update_ms)
        return self.last_update_ms

    def set_params(self, values: Mapping[str, float]) -> float:
        """Set several parameters at once and redraw."""
        start = time.perf_counter()
        self.params.update({str(k): float(v) for k, v in values.items()})
        update(self.figure, self.info, self.params, self.view_window, self.evaluator)
        self.last_update_ms = (time.perf_counter() - start) * 1000.0
        return self.last_update_ms

    def reset_params(self) -> float:
        """Reset every parameter to its default and redraw."""
        defaults = {spec.name: spec.default for spec in default_params(self.info)}
        return self.set_params(defaults)

    # ------------------------------------------------------------- shortcuts
    @property
    def line(self):
        """The plotted line (explicit equations only)."""
        return self.axes.lines[0] if self.axes.lines else None

    def y_data(self) -> np.ndarray:
        """The current y values (explicit equations only)."""
        line = self.line
        if line is None:
            return np.array([])
        return np.asarray(line.get_ydata(), dtype=float)

    def close(self) -> None:
        """Release the Matplotlib figure."""
        plt.close(self.figure)


# --------------------------------------------------------------------- plugin
def build_session(
    parsed_input: ParsedInput,
    param_values: Mapping[str, float] | None = None,
    view_window: tuple[float, float, float, float] = DEFAULT_WINDOW,
    **opts: Any,
) -> PlotSession:
    """Analyse a parsed input and return a ready to use :class:`PlotSession`."""
    expression = parsed_input.sympy_expr
    if expression is None:
        raise ParseError("The input has not been parsed yet")
    info = analyze_equation(expression)
    return PlotSession(info, param_values, view_window)


def visualize_parsed(
    parsed_input: ParsedInput,
    param_values: Mapping[str, float] | None = None,
    view_window: tuple[float, float, float, float] = DEFAULT_WINDOW,
    **opts: Any,
) -> VisualizationResult:
    """Plugin entry point: analyse the parsed input and build a figure."""
    expression = parsed_input.sympy_expr
    if expression is None:
        raise ParseError("The input has not been parsed yet")

    info = analyze_equation(expression)
    specs = default_params(info)
    values = {spec.name: spec.default for spec in specs}
    if param_values:
        values.update({str(k): float(v) for k, v in param_values.items()})

    figure = render(info, values, view_window)
    return VisualizationResult(
        figure=figure,
        image_bytes=None,
        parameters=specs,
        meta={
            "kind": info.kind,
            "latex": info.latex,
            "dependent": info.dependent,
            "variables": info.variable_names,
            "parameters": info.parameter_names(),
            "param_values": values,
        },
    )


def equation_specs() -> list[tuple[str, str, list[str]]]:
    """The equation families the test-suite checks (``(text, kind, params)``)."""
    return [
        ("y = m*x + c", "explicit_y", ["c", "m"]),
        ("y = a*x**2 + b*x + c", "explicit_y", ["a", "b", "c"]),
        ("y = x**3 - 2*x", "explicit_y", []),
        ("x**2 + y**2 = r**2", "implicit", ["r"]),
        ("x**2/4 + y**2/9 = 1", "implicit", []),
        ("y = A*sin(x)", "explicit_y", ["A"]),
        ("y = exp(x)", "explicit_y", []),
        ("y = log(x)", "explicit_y", []),
        ("y = Abs(x)", "explicit_y", []),
        ("y = 1/x", "explicit_y", []),
    ]


__all__ = [
    "ASYMPTOTE_LIMIT",
    "GRID_POINTS",
    "DEFAULT_WINDOW",
    "EquationInfo",
    "Evaluator",
    "PlotSession",
    "analyze_equation",
    "build_evaluator",
    "build_session",
    "default_params",
    "equation_specs",
    "mask_discontinuities",
    "render",
    "update",
    "visualize_parsed",
]
