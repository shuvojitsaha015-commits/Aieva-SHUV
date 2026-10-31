"""Complex numbers on the Argand plane (feature 1.c).

Headless only. The module draws the Argand diagram and computes the results of
the complex operations that are shown in the UI.
"""

from __future__ import annotations

import cmath
import math
from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import sympy  # noqa: E402
from matplotlib.patches import Arc  # noqa: E402

from aieva.core.errors import ParseError, SolveError  # noqa: E402
from aieva.core.models import ParamSpec, VisualizationResult  # noqa: E402

#: The colours used on the Argand diagram.
AXIS_COLOR = "#444444"
POINT_COLOR = "#1f77b4"
RESULT_COLOR = "#d62728"
UNIT_COLOR = "#2ca02c"


def parse_complex(text: str) -> complex:
    """Parse ``3 + 4i`` (also ``3+4j``, ``-2i``, ``5``)."""
    if text is None:
        raise ParseError("No complex number given")
    cleaned = text.strip().replace(" ", "").replace("*", "")
    if not cleaned:
        raise ParseError("No complex number given")
    cleaned = cleaned.replace("i", "j")
    try:
        return complex(cleaned)
    except ValueError:
        pass
    # forms like "3+4i" written without a sign: "34i" is not valid anyway
    raise ParseError(f"Could not read the complex number {text!r}")


def format_complex(value: complex) -> str:
    """A readable representation of a complex number."""
    real = value.real
    imaginary = value.imag
    if abs(imaginary) < 1e-12:
        return f"{real:g}"
    if abs(real) < 1e-12:
        return f"{imaginary:g}i"
    sign = "+" if imaginary >= 0 else "-"
    return f"{real:g} {sign} {abs(imaginary):g}i"


def argand_view(
    z: complex | str,
    operation: str = "none",
    w: complex | str | None = None,
    n: int = 3,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw the Argand diagram of ``z`` (and of the requested operation)."""
    if isinstance(z, str):
        z = parse_complex(z)
    if isinstance(w, str):
        w = parse_complex(w)
    if w is None:
        w = complex(1.0, 1.0)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    limit = max(abs(z), abs(w), 1.0) * 1.6
    ax.axhline(0, color=AXIS_COLOR, linewidth=1.0)
    ax.axvline(0, color=AXIS_COLOR, linewidth=1.0)
    ax.grid(True, alpha=0.25)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Re")
    ax.set_ylabel("Im")
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)

    circle = plt.Circle((0, 0), 1.0, fill=False, color=UNIT_COLOR, linestyle=":", linewidth=1.4)
    ax.add_patch(circle)
    ax.plot([-1.0, 1.0], [0, 0], color=UNIT_COLOR, linewidth=0.8, alpha=0.6)
    ax.plot([0, 0], [-1.0, 1.0], color=UNIT_COLOR, linewidth=0.8, alpha=0.6)

    _draw_vector(ax, z, POINT_COLOR, "z")
    annotation = f"z = {format_complex(z)}\n|z| = {abs(z):.6g}\narg(z) = {math.degrees(cmath.phase(z)):.4g} deg"

    result = z
    roots: list[complex] = []
    if operation == "add":
        result = z + w
        _draw_vector(ax, w, "#ff7f0e", "w")
        _draw_vector(ax, z, POINT_COLOR, "z", origin=(w.real, w.imag))
        _draw_vector(ax, result, RESULT_COLOR, "z + w")
        annotation += f"\nz + w = {format_complex(result)}"
    elif operation == "multiply":
        result = z * w
        _draw_vector(ax, w, "#ff7f0e", "w")
        _draw_vector(ax, result, RESULT_COLOR, "z * w")
        annotation += (
            f"\nz * w = {format_complex(result)}\n"
            f"rotation by {math.degrees(cmath.phase(w)):.4g} deg, scale by {abs(w):.6g}"
        )
    elif operation == "multiply_i":
        result = z * 1j
        _draw_vector(ax, result, RESULT_COLOR, "z * i")
        annotation += f"\nz * i = {format_complex(result)}  (90 deg rotation)"
    elif operation == "conjugate":
        result = z.conjugate()
        _draw_vector(ax, result, RESULT_COLOR, "conj(z)")
        annotation += f"\nconj(z) = {format_complex(result)}"
    elif operation == "power":
        exponent = int(n)
        result = z**exponent
        _draw_vector(ax, result, RESULT_COLOR, f"z^{exponent}")
        annotation += f"\nz^{exponent} = {format_complex(result)}"
    elif operation == "roots":
        exponent = max(int(n), 1)
        radius = abs(z) ** (1.0 / exponent)
        roots = [
            radius * cmath.exp((cmath.phase(z) + 2.0 * math.pi * index) / exponent)
            for index in range(exponent)
        ]
        roots = list(roots)
        for index, root in enumerate(roots):
            _draw_vector(ax, root, RESULT_COLOR, f"root {index + 1}")
        annotation += "\nroots: " + ", ".join(format_complex(root) for root in roots)
        result = roots[0]
    elif operation != "none":
        raise SolveError(f"Unknown complex operation {operation!r}")

    # the angle arc of z
    if abs(z) > 1e-12:
        angle = math.degrees(cmath.phase(z))
        ax.add_patch(
            Arc((0, 0), 1.0, 1.0, angle=0, theta1=0, theta2=angle, color=POINT_COLOR, linewidth=2.0)
        )

    ax.text(
        0.03,
        0.97,
        annotation,
        transform=ax.transAxes,
        fontsize=10,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
    )
    fig.subplots_adjust(left=0.14, right=0.95, top=0.90, bottom=0.12)

    return VisualizationResult(
        figure=fig,
        parameters=[ParamSpec(name="n", default=float(n), min=1.0, max=12.0, step=1.0)],
        meta={
            "kind": "complex",
            "operation": operation,
            "z": format_complex(z),
            "w": format_complex(w),
            "result": format_complex(result),
            "modulus": abs(z),
            "argument_deg": math.degrees(cmath.phase(z)),
            "roots": [(root.real, root.imag) for root in roots],
            "annotation": annotation,
            "warnings": [],
        },
    )


def _draw_vector(
    ax: Any, value: complex, color: str, label: str = "", origin: tuple[float, float] = (0.0, 0.0)
) -> None:
    ax.quiver(
        origin[0],
        origin[1],
        value.real,
        value.imag,
        angles="xy",
        scale_units="xy",
        scale=1,
        color=color,
        width=0.008,
        zorder=3,
    )
    ax.plot([origin[0]], [origin[1]], "o", color=color, markersize=5, zorder=4)
    if label:
        ax.text(
            origin[0] + value.real * 1.06,
            origin[1] + value.imag * 1.06,
            label,
            color=color,
            fontsize=11,
            fontweight="bold",
        )


def domain_coloring(
    expression: str,
    size: int = 60,
    figsize: tuple[float, float] = (6.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """The optional domain colouring of ``f(z)`` (stretch goal, behind a flag)."""
    from aieva.core.safe_parse import parse_text_expression

    expr = parse_text_expression(expression)
    symbol = next(iter(expr.free_symbols), None)
    if symbol is None:
        raise SolveError("The expression needs a complex variable")

    func = sympy.lambdify(symbol, expr, modules=["numpy"])
    real = np.linspace(-2.0, 2.0, size)
    imag = np.linspace(-2.0, 2.0, size)
    grid = np.array([[complex(r, i) for i in imag] for r in real])
    with np.errstate(all="ignore"):
        values = np.asarray(func(grid), dtype=complex)
    magnitude = np.abs(values)
    phase = np.angle(values)
    hue = (phase + math.pi) / (2.0 * math.pi)
    saturation = 1.0 - 1.0 / (1.0 + magnitude)
    largest = float(magnitude.max()) if magnitude.size else 1.0
    value = np.clip(magnitude / (largest or 1.0), 0.0, 1.0)

    from matplotlib.colors import hsv_to_rgb

    rgb = hsv_to_rgb(np.stack([hue, saturation, value], axis=-1))

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.imshow(rgb, extent=(-2.0, 2.0, -2.0, 2.0), origin="lower")
    ax.set_title(f"domain colouring of {expression}")
    ax.set_xlabel("Re")
    ax.set_ylabel("Im")
    fig.subplots_adjust(left=0.14, right=0.95, top=0.90, bottom=0.12)

    return VisualizationResult(
        figure=fig,
        parameters=[],
        meta={"kind": "domain_coloring", "expression": expression, "warnings": []},
    )


__all__ = [
    "argand_view",
    "domain_coloring",
    "format_complex",
    "parse_complex",
]
