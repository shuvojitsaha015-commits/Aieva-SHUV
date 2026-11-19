"""2D and 3D plotting (feature 1.d).

Headless only - the module produces Matplotlib figures and plain data. The
Kivy widget :mod:`aieva.ui.widgets.plot3d_view` only rotates and zooms the
figure that is built here.

Supported inputs
----------------
``z = x**2 + y**2``                a surface in 3D
``x = cos(t), y = sin(t), z = t``  a parametric curve in 3D
``x = u*cos(v), y = u*sin(v), z = u``  a parametric surface in 3D
``r = 1 + cos(theta)``             a polar plot in 2D
``x = cos(t), y = sin(t)``         a parametric plot in 2D
``y = sin(x)``                     a function plot in 2D
"""

from __future__ import annotations

import math
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

import numpy as np  # noqa: E402
import sympy  # noqa: E402

from aieva.core.errors import ParseError, SolveError  # noqa: E402
from aieva.core.models import ParamSpec, VisualizationResult  # noqa: E402
from aieva.core.plotting import new_figure, new_subplots  # noqa: E402
from aieva.core.safe_parse import parse_text_expression  # noqa: E402

#: The mesh resolution per quality level.
QUALITY_LEVELS: dict[str, int] = {"low": 30, "medium": 60, "high": 120}

#: The quality that is used when nothing else is asked for.
DEFAULT_QUALITY = "medium"

#: The number of points used for a curve.
CURVE_POINTS = 400

#: Values above this magnitude are masked out (poles).
VALUE_LIMIT = 1.0e6

#: The default parameter windows of the 2D / 3D plots.
DEFAULT_RANGES: dict[str, tuple[float, float]] = {
    "x": (-6.0, 6.0),
    "y": (-6.0, 6.0),
    "z": (-6.0, 6.0),
    "u": (0.0, 2.0 * math.pi),
    "v": (0.0, 2.0 * math.pi),
    "t": (0.0, 2.0 * math.pi),
    "theta": (0.0, 2.0 * math.pi),
}

_ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.+?)\s*$")


# --------------------------------------------------------------------- parsing
@dataclass
class PlotSpec:
    """What the user asked for."""

    kind: str
    dimension: str
    expressions: dict[str, sympy.Basic] = field(default_factory=dict)
    variables: list[sympy.Symbol] = field(default_factory=list)
    parameters: list[sympy.Symbol] = field(default_factory=list)
    title: str = ""

    @property
    def variable_names(self) -> list[str]:
        return [symbol.name for symbol in self.variables]

    @property
    def parameter_names(self) -> list[str]:
        return [symbol.name for symbol in self.parameters]


def split_assignments(text: str) -> list[str]:
    """Split ``x = 1, y = 2`` on the top level commas and semicolons."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if depth == 0 and char in ";,":
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def _parse_assignments(text: str) -> dict[str, sympy.Basic]:
    if not text or not text.strip():
        raise ParseError("Nothing to plot")
    assignments: dict[str, sympy.Basic] = {}
    for part in split_assignments(text):
        match = _ASSIGNMENT_RE.match(part)
        if not match:
            raise ParseError(f"Could not read {part!r} - use 'name = expression'")
        name, body = match.group(1), match.group(2)
        if "=" in body:
            raise ParseError(f"Only one '=' per part, got {part!r}")
        assignments[name] = parse_text_expression(body)
    if not assignments:
        raise ParseError("Nothing to plot")
    return assignments


def parse_plot_spec(text: str) -> PlotSpec:
    """Work out what kind of plot the text asks for."""
    assignments = _parse_assignments(text)
    names = set(assignments)
    free = set()
    for expression in assignments.values():
        free |= expression.free_symbols

    has_x = "x" in names
    has_y = "y" in names
    has_z = "z" in names
    has_r = "r" in names

    if has_z and has_x and has_y:
        # parametric curve or parametric surface in 3D
        variables = sorted(
            (symbol for symbol in free if symbol.name in ("t", "u", "v")),
            key=lambda s: s.name,
        )
        if len(variables) == 1:
            kind = "curve3d"
        elif len(variables) >= 2:
            kind = "surface3d"
            variables = variables[:2]
        else:
            raise ParseError("A 3D curve needs a parameter such as t")
        parameters = sorted(free - set(variables), key=lambda s: s.name)
        return PlotSpec(
            kind, "3d", assignments, variables, parameters, title="parametric curve in 3D"
        )

    if has_z:
        # z = f(x, y)
        expression = assignments["z"]
        axes = [sympy.Symbol("x"), sympy.Symbol("y")]
        missing = [axis for axis in axes if axis not in expression.free_symbols]
        if len(missing) == 2:
            raise ParseError("A surface needs both x and y, for example z = x**2 + y**2")
        parameters = sorted(free - set(axes), key=lambda s: s.name)
        return PlotSpec("surface", "3d", assignments, axes, parameters, title="surface z = f(x, y)")

    if has_r or sympy.Symbol("theta") in free:
        expression = assignments.get("r")
        if expression is None:
            expression = parse_text_expression(text)
        variables = [sympy.Symbol("theta")]
        parameters = sorted(expression.free_symbols - set(variables), key=lambda s: s.name)
        return PlotSpec("polar", "2d", {"r": expression}, variables, parameters, title="polar plot")

    if has_x and has_y:
        variables = sorted(
            (symbol for symbol in free if symbol.name in ("t", "u", "v")),
            key=lambda s: s.name,
        )
        if not variables:
            raise ParseError("A parametric plot needs a parameter such as t")
        variables = variables[:1]
        parameters = sorted(free - set(variables), key=lambda s: s.name)
        return PlotSpec(
            "parametric2d", "2d", assignments, variables, parameters, title="parametric plot"
        )

    expression = assignments.get("y")
    if expression is None:
        expression = next(iter(assignments.values()))
    variables = [sympy.Symbol("x")] if sympy.Symbol("x") in expression.free_symbols else []
    if not variables:
        variables = sorted(expression.free_symbols, key=lambda s: s.name)[:1]
    parameters = sorted(expression.free_symbols - set(variables), key=lambda s: s.name)
    return PlotSpec("function2d", "2d", assignments, variables, parameters, title="function plot")


def detect_dimension(text: str) -> str:
    """``"3d"`` when the text asks for a 3D plot, otherwise ``"2d"``."""
    return parse_plot_spec(text).dimension


# ------------------------------------------------------------------ rendering
def _mesh_size(quality: str) -> int:
    if quality not in QUALITY_LEVELS:
        raise SolveError(f"Unknown quality {quality!r} - use one of {sorted(QUALITY_LEVELS)}")
    return QUALITY_LEVELS[quality]


def _mask(values: np.ndarray) -> np.ma.MaskedArray:
    """Mask NaN, infinite and absurdly large values."""
    masked = np.ma.masked_invalid(values)
    return np.ma.masked_outside(masked, -VALUE_LIMIT, VALUE_LIMIT)


def _parameter_values(
    parameters: list[sympy.Symbol], values: Mapping[str, float] | None
) -> list[float]:
    values = values or {}
    return [float(values.get(symbol.name, 1.0)) for symbol in parameters]


def _range_for(name: str, override: tuple[float, float] | None) -> tuple[float, float]:
    if override is not None:
        return (float(override[0]), float(override[1]))
    return DEFAULT_RANGES.get(name, (-6.0, 6.0))


def _lambda(function: sympy.Basic, arguments: list[sympy.Symbol]) -> Callable[..., Any]:
    return sympy.lambdify(arguments, function, modules=["numpy"])


def _surface_data(
    expression: sympy.Basic,
    parameters: list[sympy.Symbol],
    values: Mapping[str, float] | None,
    quality: str,
    x_range: tuple[float, float] | None = None,
    y_range: tuple[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    size = _mesh_size(quality)
    x_min, x_max = _range_for("x", x_range)
    y_min, y_max = _range_for("y", y_range)
    x_values = np.linspace(x_min, x_max, size)
    y_values = np.linspace(y_min, y_max, size)
    x_grid, y_grid = np.meshgrid(x_values, y_values)
    function = _lambda(expression, [sympy.Symbol("x"), sympy.Symbol("y")] + parameters)
    with np.errstate(all="ignore"):
        z_values = np.asarray(
            function(x_grid, y_grid, *_parameter_values(parameters, values)), dtype=float
        )
    return x_grid, y_grid, _mask(z_values)


def _style_3d(ax: Any, title: str) -> None:
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.set_title(title)
    try:
        ax.set_box_aspect((1, 1, 0.7))
    except Exception:  # pragma: no cover - very old matplotlib
        pass


def surface_view(
    expression: str | sympy.Basic,
    quality: str = DEFAULT_QUALITY,
    show_wireframe: bool = False,
    show_contour: bool = False,
    parameters: Mapping[str, float] | None = None,
    x_range: tuple[float, float] | None = None,
    y_range: tuple[float, float] | None = None,
    figsize: tuple[float, float] = (7.0, 6.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw the surface ``z = f(x, y)``."""
    if isinstance(expression, str):
        expression = parse_text_expression(expression)
    parameter_symbols = sorted(
        expression.free_symbols - {sympy.Symbol("x"), sympy.Symbol("y")}, key=lambda s: s.name
    )
    x_grid, y_grid, z_values = _surface_data(
        expression, parameter_symbols, parameters, quality, x_range, y_range
    )

    fig = new_figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    surface = ax.plot_surface(
        x_grid, y_grid, z_values, cmap="viridis", alpha=0.9, linewidth=0, antialiased=True
    )
    if show_wireframe:
        ax.plot_wireframe(
            x_grid, y_grid, z_values, rstride=4, cstride=4, linewidth=0.4, alpha=0.45, color="k"
        )
    if show_contour:
        finite = z_values.compressed()
        if finite.size:
            offset = float(np.min(finite))
            ax.contour(x_grid, y_grid, z_values, zdir="z", offset=offset, cmap="magma", levels=12)
    fig.colorbar(surface, ax=ax, shrink=0.6, label="z")
    _style_3d(ax, "z = f(x, y)")
    fig.subplots_adjust(left=0.02, right=0.92, top=0.93, bottom=0.04)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name=symbol.name, default=1.0, min=-5.0, max=5.0, step=0.05)
            for symbol in parameter_symbols
        ],
        meta={
            "kind": "surface",
            "dimension": "3d",
            "quality": quality,
            "mesh": _mesh_size(quality),
            "wireframe": show_wireframe,
            "contour": show_contour,
            "warnings": [],
        },
    )


def parametric_curve_view(
    equations: Mapping[str, str] | str,
    quality: str = DEFAULT_QUALITY,
    parameter: str = "t",
    t_range: tuple[float, float] | None = None,
    parameters: Mapping[str, float] | None = None,
    figsize: tuple[float, float] = (7.0, 6.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw a parametric curve in 3D (``x = ..., y = ..., z = ...``)."""
    if isinstance(equations, str):
        assignments = _parse_assignments(equations)
    else:
        assignments = {name: parse_text_expression(body) for name, body in equations.items()}
    for name in ("x", "y", "z"):
        if name not in assignments:
            raise ParseError(f"A 3D curve needs x, y and z - {name} is missing")

    variable = sympy.Symbol(parameter)
    free = set()
    for expression in assignments.values():
        free |= expression.free_symbols
    parameter_symbols = sorted(free - {variable}, key=lambda s: s.name)

    t_min, t_max = _range_for(parameter, t_range)
    count = CURVE_POINTS if quality != "low" else CURVE_POINTS // 2
    t_values = np.linspace(t_min, t_max, count)
    functions = {
        name: _lambda(expression, [variable] + parameter_symbols)
        for name, expression in assignments.items()
    }
    extra = _parameter_values(parameter_symbols, parameters)
    with np.errstate(all="ignore"):
        x_values = np.asarray(functions["x"](t_values, *extra), dtype=float)
        y_values = np.asarray(functions["y"](t_values, *extra), dtype=float)
        z_values = np.asarray(functions["z"](t_values, *extra), dtype=float)

    fig = new_figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.plot(_mask(x_values), _mask(y_values), _mask(z_values), color="#1f77b4", linewidth=2)
    ax.set_title(f"parametric curve ({parameter} from {t_min:g} to {t_max:g})")
    _style_3d(ax, "parametric curve")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.04)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name=symbol.name, default=1.0, min=-5.0, max=5.0, step=0.05)
            for symbol in parameter_symbols
        ],
        meta={
            "kind": "curve3d",
            "dimension": "3d",
            "quality": quality,
            "points": int(count),
            "warnings": [],
        },
    )


def parametric_surface_view(
    equations: Mapping[str, str] | str,
    quality: str = DEFAULT_QUALITY,
    u_range: tuple[float, float] | None = None,
    v_range: tuple[float, float] | None = None,
    parameters: Mapping[str, float] | None = None,
    figsize: tuple[float, float] = (7.0, 6.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw a parametric surface in 3D (``x = ..., y = ..., z = ...`` in u, v)."""
    if isinstance(equations, str):
        assignments = _parse_assignments(equations)
    else:
        assignments = {name: parse_text_expression(body) for name, body in equations.items()}
    for name in ("x", "y", "z"):
        if name not in assignments:
            raise ParseError(f"A parametric surface needs x, y and z - {name} is missing")

    free = set()
    for expression in assignments.values():
        free |= expression.free_symbols
    variables = sorted(
        (symbol for symbol in free if symbol.name in ("u", "v")), key=lambda s: s.name
    )[:2]
    if len(variables) < 2:
        raise ParseError("A parametric surface needs the parameters u and v")
    parameter_symbols = sorted(free - set(variables), key=lambda s: s.name)

    size = _mesh_size(quality)
    u_min, u_max = _range_for("u", u_range)
    v_min, v_max = _range_for("v", v_range)
    u_values = np.linspace(u_min, u_max, size)
    v_values = np.linspace(v_min, v_max, size)
    u_grid, v_grid = np.meshgrid(u_values, v_values)
    extra = _parameter_values(parameter_symbols, parameters)
    values: dict[str, np.ndarray] = {}
    for name, expression in assignments.items():
        function = _lambda(expression, variables + parameter_symbols)
        with np.errstate(all="ignore"):
            values[name] = np.asarray(function(u_grid, v_grid, *extra), dtype=float)

    fig = new_figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(
        _mask(values["x"]),
        _mask(values["y"]),
        _mask(values["z"]),
        cmap="viridis",
        alpha=0.9,
        linewidth=0,
        antialiased=True,
    )
    _style_3d(ax, "parametric surface")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.04)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name=symbol.name, default=1.0, min=-5.0, max=5.0, step=0.05)
            for symbol in parameter_symbols
        ],
        meta={
            "kind": "surface3d",
            "dimension": "3d",
            "quality": quality,
            "mesh": size,
            "warnings": [],
        },
    )


def polar_view(
    expression: str | sympy.Basic,
    quality: str = DEFAULT_QUALITY,
    theta_range: tuple[float, float] | None = None,
    parameters: Mapping[str, float] | None = None,
    figsize: tuple[float, float] = (7.0, 6.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw a polar plot ``r = f(theta)``."""
    if isinstance(expression, str):
        expression = parse_text_expression(expression)
    variable = sympy.Symbol("theta")
    parameter_symbols = sorted(expression.free_symbols - {variable}, key=lambda s: s.name)

    theta_min, theta_max = _range_for("theta", theta_range)
    count = CURVE_POINTS if quality != "low" else CURVE_POINTS // 2
    theta_values = np.linspace(theta_min, theta_max, count)
    function = _lambda(expression, [variable] + parameter_symbols)
    with np.errstate(all="ignore"):
        radii = np.asarray(
            function(theta_values, *_parameter_values(parameter_symbols, parameters)), dtype=float
        )
    radii = np.ma.masked_invalid(radii)
    x_values = _mask(radii * np.cos(theta_values))
    y_values = _mask(radii * np.sin(theta_values))

    fig, ax = new_subplots(figsize=figsize, dpi=dpi)
    ax.plot(x_values, y_values, color="#1f77b4", linewidth=2)
    ax.axhline(0, color="0.4", linewidth=0.8)
    ax.axvline(0, color="0.4", linewidth=0.8)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("r = f(theta)")
    fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.10)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name=symbol.name, default=1.0, min=-5.0, max=5.0, step=0.05)
            for symbol in parameter_symbols
        ],
        meta={
            "kind": "polar",
            "dimension": "2d",
            "quality": quality,
            "points": int(count),
            "warnings": [],
        },
    )


def parametric_2d_view(
    equations: Mapping[str, str] | str,
    quality: str = DEFAULT_QUALITY,
    parameter: str = "t",
    t_range: tuple[float, float] | None = None,
    parameters: Mapping[str, float] | None = None,
    figsize: tuple[float, float] = (7.0, 6.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw a parametric plot in 2D (``x = ..., y = ...``)."""
    if isinstance(equations, str):
        assignments = _parse_assignments(equations)
    else:
        assignments = {name: parse_text_expression(body) for name, body in equations.items()}
    for name in ("x", "y"):
        if name not in assignments:
            raise ParseError(f"A parametric plot needs x and y - {name} is missing")

    variable = sympy.Symbol(parameter)
    free = set()
    for expression in assignments.values():
        free |= expression.free_symbols
    parameter_symbols = sorted(free - {variable}, key=lambda s: s.name)

    t_min, t_max = _range_for(parameter, t_range)
    count = CURVE_POINTS if quality != "low" else CURVE_POINTS // 2
    t_values = np.linspace(t_min, t_max, count)
    extra = _parameter_values(parameter_symbols, parameters)
    with np.errstate(all="ignore"):
        x_values = np.asarray(
            _lambda(assignments["x"], [variable] + parameter_symbols)(t_values, *extra), dtype=float
        )
        y_values = np.asarray(
            _lambda(assignments["y"], [variable] + parameter_symbols)(t_values, *extra), dtype=float
        )

    fig, ax = new_subplots(figsize=figsize, dpi=dpi)
    ax.plot(_mask(x_values), _mask(y_values), color="#1f77b4", linewidth=2)
    ax.axhline(0, color="0.4", linewidth=0.8)
    ax.axvline(0, color="0.4", linewidth=0.8)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title(f"parametric curve ({parameter} from {t_min:g} to {t_max:g})")
    fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.10)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name=symbol.name, default=1.0, min=-5.0, max=5.0, step=0.05)
            for symbol in parameter_symbols
        ],
        meta={
            "kind": "parametric2d",
            "dimension": "2d",
            "quality": quality,
            "points": int(count),
            "warnings": [],
        },
    )


def render_spec(
    spec: PlotSpec,
    quality: str = DEFAULT_QUALITY,
    parameters: Mapping[str, float] | None = None,
    show_wireframe: bool = False,
    show_contour: bool = False,
) -> VisualizationResult:
    """Render a parsed :class:`PlotSpec`."""
    if spec.kind == "surface":
        return surface_view(
            spec.expressions["z"],
            quality=quality,
            show_wireframe=show_wireframe,
            show_contour=show_contour,
            parameters=parameters,
        )
    if spec.kind == "curve3d":
        return parametric_curve_view(spec.expressions, quality=quality, parameters=parameters)
    if spec.kind == "surface3d":
        return parametric_surface_view(spec.expressions, quality=quality, parameters=parameters)
    if spec.kind == "polar":
        return polar_view(spec.expressions["r"], quality=quality, parameters=parameters)
    if spec.kind == "parametric2d":
        return parametric_2d_view(spec.expressions, quality=quality, parameters=parameters)
    expression = spec.expressions.get("y") or next(iter(spec.expressions.values()))
    return _function_2d_view(expression, quality=quality, parameters=parameters)


def _function_2d_view(
    expression: sympy.Basic,
    quality: str = DEFAULT_QUALITY,
    parameters: Mapping[str, float] | None = None,
    figsize: tuple[float, float] = (7.0, 6.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw a plain 2D function ``y = f(x)``."""
    variable = sympy.Symbol("x")
    parameter_symbols = sorted(expression.free_symbols - {variable}, key=lambda s: s.name)
    x_min, x_max = DEFAULT_RANGES["x"]
    count = CURVE_POINTS if quality != "low" else CURVE_POINTS // 2
    x_values = np.linspace(x_min, x_max, count)
    function = _lambda(expression, [variable] + parameter_symbols)
    with np.errstate(all="ignore"):
        y_values = np.asarray(
            function(x_values, *_parameter_values(parameter_symbols, parameters)), dtype=float
        )
    y_values = _mask(y_values)
    # mask the poles of a rational function
    jumps = np.abs(np.diff(np.nan_to_num(y_values.filled(np.nan), nan=0.0)))
    limit = float(np.nanmax(jumps)) if jumps.size else 0.0
    if limit > 10 * (np.nanmax(np.abs(y_values.compressed())) or 1.0):
        y_values = np.ma.masked_where(jumps > limit / 2.0, y_values)

    fig, ax = new_subplots(figsize=figsize, dpi=dpi)
    ax.plot(x_values, y_values, color="#1f77b4", linewidth=2)
    ax.axhline(0, color="0.4", linewidth=0.8)
    ax.axvline(0, color="0.4", linewidth=0.8)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("y = f(x)")
    fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.10)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name=symbol.name, default=1.0, min=-5.0, max=5.0, step=0.05)
            for symbol in parameter_symbols
        ],
        meta={
            "kind": "function2d",
            "dimension": "2d",
            "quality": quality,
            "points": int(count),
            "warnings": [],
        },
    )


# --------------------------------------------------------------------- session
class Plot3DSession:
    """A 3D plot that can be rotated, zoomed and re-parameterised.

    The surface is computed once; rotating only changes the view, which keeps
    the drag at board speed. During an interaction the mesh can be lowered
    (the "low" quality) and restored on touch up.
    """

    def __init__(
        self,
        spec: PlotSpec | str,
        quality: str = DEFAULT_QUALITY,
        parameters: Mapping[str, float] | None = None,
        show_wireframe: bool = False,
        show_contour: bool = False,
    ) -> None:
        self.spec = parse_plot_spec(spec) if isinstance(spec, str) else spec
        self.quality = quality
        self.show_wireframe = show_wireframe
        self.show_contour = show_contour
        self.parameter_values: dict[str, float] = dict(parameters or {})
        self.elevation = 30.0
        self.azimuth = -60.0
        self.zoom = 1.0
        self.auto_rotate = False
        self.interacting = False
        self.last_render_ms = 0.0
        self._refresh()

    # ------------------------------------------------------------------ api
    @property
    def figure(self):
        return self._result.figure

    @property
    def axes(self):
        return self._result.figure.axes[0] if self._result.figure is not None else None

    @property
    def parameters(self) -> list[ParamSpec]:
        return self._result.parameters

    def set_param(self, name: str, value: float) -> float:
        """Set a parameter and redraw. Returns the render time in ms."""
        self.parameter_values[name] = float(value)
        return self._refresh()

    def set_quality(self, quality: str) -> float:
        """Change the mesh quality and redraw."""
        self.quality = quality
        return self._refresh()

    def set_options(
        self, show_wireframe: bool | None = None, show_contour: bool | None = None
    ) -> float:
        """Toggle the wireframe / contour projection and redraw."""
        if show_wireframe is not None:
            self.show_wireframe = show_wireframe
        if show_contour is not None:
            self.show_contour = show_contour
        return self._refresh()

    # ------------------------------------------------------------------ view
    def set_view(
        self,
        elevation: float | None = None,
        azimuth: float | None = None,
        zoom: float | None = None,
    ) -> None:
        """Rotate or zoom the camera (cheap - no re-computation)."""
        if elevation is not None:
            self.elevation = float(elevation) % 360.0
        if azimuth is not None:
            self.azimuth = float(azimuth) % 360.0
        if zoom is not None:
            self.zoom = min(max(float(zoom), 0.4), 3.0)
        self._apply_view()

    def rotate(self, d_elevation: float = 0.0, d_azimuth: float = 0.0) -> None:
        """Rotate the camera by a relative amount."""
        self.set_view(elevation=self.elevation + d_elevation, azimuth=self.azimuth + d_azimuth)

    def zoom_by(self, factor: float) -> None:
        """Zoom in (factor > 1) or out (factor < 1)."""
        self.set_view(zoom=self.zoom * factor)

    def reset_view(self) -> None:
        """Back to the default camera."""
        self.set_view(elevation=30.0, azimuth=-60.0, zoom=1.0)

    def step_auto_rotate(self, delta_seconds: float = 0.05) -> None:
        """One step of the automatic rotation."""
        if not self.auto_rotate:
            return
        self.set_view(azimuth=self.azimuth + 30.0 * delta_seconds)

    # --------------------------------------------------------- interaction
    def begin_interaction(self) -> float:
        """Lower the mesh quality while the user drags."""
        self.interacting = True
        self._quality_before_interaction = self.quality
        if self.quality != "low":
            return self.set_quality("low")
        return 0.0

    def end_interaction(self) -> float:
        """Restore the full quality after the drag."""
        self.interacting = False
        quality = getattr(self, "_quality_before_interaction", self.quality)
        self._quality_before_interaction = quality
        if self.quality != quality:
            return self.set_quality(quality)
        return 0.0

    # ------------------------------------------------------------ internals
    def _refresh(self) -> float:
        """Render the figure again and restore the camera. Returns the ms."""
        self._result = self._render()
        self._apply_view()
        return self.last_render_ms

    def _render(self) -> VisualizationResult:
        started = time.perf_counter()
        result = render_spec(
            self.spec,
            quality=self.quality,
            parameters=self.parameter_values,
            show_wireframe=self.show_wireframe,
            show_contour=self.show_contour,
        )
        self.last_render_ms = (time.perf_counter() - started) * 1000.0
        return result

    def _apply_view(self) -> None:
        axes = self.axes
        if axes is None:
            return
        try:
            axes.view_init(elev=self.elevation, azim=self.azimuth)
        except Exception:  # pragma: no cover - 2D axes have no view_init
            return
        try:
            axes.set_box_aspect((1, 1, 0.7), zoom=self.zoom)
        except Exception:  # pragma: no cover - older matplotlib
            pass


__all__ = [
    "DEFAULT_QUALITY",
    "QUALITY_LEVELS",
    "Plot3DSession",
    "PlotSpec",
    "detect_dimension",
    "parametric_2d_view",
    "parametric_curve_view",
    "parametric_surface_view",
    "parse_plot_spec",
    "polar_view",
    "render_spec",
    "surface_view",
]
