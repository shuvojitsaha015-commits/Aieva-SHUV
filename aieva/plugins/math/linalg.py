"""Vectors, matrices, eigen values and systems of equations (feature 1.c).

Headless only - the module produces Matplotlib figures and plain data.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import sympy  # noqa: E402
from matplotlib.patches import Arc, Polygon  # noqa: E402

from aieva.core.errors import ParseError, SolveError  # noqa: E402
from aieva.core.models import ParamSpec, VisualizationResult  # noqa: E402

#: Number of grid lines per direction in the matrix transformation view.
GRID_LINES = 21

#: The size of the reference square / cube.
UNIT_SIZE = 1.0

_VECTOR_RE = re.compile(r"([A-Za-z_][A-Za-z_0-9]*)\s*=\s*\(([^)]*)\)")


# ---------------------------------------------------------------------- vectors
@dataclass
class VectorSpec:
    """A named vector."""

    name: str
    values: list[float] = field(default_factory=list)

    @property
    def dimension(self) -> int:
        return len(self.values)

    @property
    def array(self) -> np.ndarray:
        return np.asarray(self.values, dtype=float)

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.name} = ({', '.join(f'{value:g}' for value in self.values)})"


def parse_vectors(text: str) -> list[VectorSpec]:
    """Parse ``a=(1,2), b=(3,1)`` into vectors."""
    if not text or not text.strip():
        raise ParseError("No vectors given")
    vectors: list[VectorSpec] = []
    for name, body in _VECTOR_RE.findall(text):
        parts = [part.strip() for part in body.split(",") if part.strip()]
        try:
            values = [float(part) for part in parts]
        except ValueError as exc:
            raise ParseError(f"Could not read the vector {name!r}") from exc
        if len(values) not in (2, 3):
            raise ParseError(f"The vector {name!r} must have 2 or 3 components")
        vectors.append(VectorSpec(name=name, values=values))
    if not vectors:
        raise ParseError("Use the notation a=(1,2), b=(3,1)")
    return vectors


def _quiver(
    ax: Any,
    vector: np.ndarray,
    color: str,
    label: str = "",
    origin: Sequence[float] = (0.0, 0.0),
    zorder: int = 3,
) -> None:
    ax.quiver(
        origin[0],
        origin[1],
        vector[0],
        vector[1],
        angles="xy",
        scale_units="xy",
        scale=1,
        color=color,
        width=0.008,
        zorder=zorder,
    )
    if label:
        ax.text(
            origin[0] + vector[0] * 1.08,
            origin[1] + vector[1] * 1.08,
            label,
            color=color,
            fontsize=11,
            fontweight="bold",
        )


def vector_view(
    vectors: Sequence[VectorSpec] | str,
    operation: str = "add",
    scale: float = 2.0,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Draw a vector operation.

    ``operation`` is one of ``add``, ``subtract``, ``scale``, ``dot``, ``cross``.
    """
    if isinstance(vectors, str):
        vectors = parse_vectors(vectors)
    vectors = list(vectors)
    if len(vectors) < 2 and operation in ("add", "subtract", "dot", "cross"):
        raise SolveError("This operation needs at least two vectors")

    first = vectors[0].array
    second = vectors[1].array
    dimension = first.size

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.axhline(0, color="0.4", linewidth=0.9)
    ax.axvline(0, color="0.4", linewidth=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    title = ""
    annotation = ""

    if operation == "add":
        result = first + second
        _quiver(ax, first, "#1f77b4", vectors[0].name)
        _quiver(ax, second, "#ff7f0e", vectors[1].name, origin=first)
        _quiver(ax, result, "#2ca02c", f"{vectors[0].name}+{vectors[1].name}")
        title = "vector addition (parallelogram rule)"
        annotation = (
            f"{vectors[0].name} + {vectors[1].name} = {np.array2string(result, precision=4)}"
        )
    elif operation == "subtract":
        result = first - second
        _quiver(ax, first, "#1f77b4", vectors[0].name)
        _quiver(ax, second, "#ff7f0e", vectors[1].name)
        _quiver(ax, result, "#d62728", f"{vectors[0].name}-{vectors[1].name}")
        title = "vector subtraction"
        annotation = (
            f"{vectors[0].name} - {vectors[1].name} = {np.array2string(result, precision=4)}"
        )
    elif operation == "scale":
        result = first * scale
        _quiver(ax, first, "#1f77b4", vectors[0].name)
        _quiver(ax, result, "#2ca02c", f"{scale:g}*{vectors[0].name}")
        title = "scalar multiplication"
        annotation = f"{scale:g} * {vectors[0].name} = {np.array2string(result, precision=4)}"
    elif operation == "dot":
        dot_value = float(np.dot(first, second))
        norm_first = float(np.linalg.norm(first))
        norm_second = float(np.linalg.norm(second))
        cosine = dot_value / (norm_first * norm_second) if norm_first and norm_second else 0.0
        angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        projection = (dot_value / (norm_first**2)) * first if norm_first else first * 0
        _quiver(ax, first, "#1f77b4", vectors[0].name)
        _quiver(ax, second, "#ff7f0e", vectors[1].name)
        _quiver(ax, projection, "#2ca02c", "projection")
        ax.add_patch(
            Arc((0, 0), 1.0, 1.0, angle=0, theta1=0, theta2=angle, color="#9467bd", linewidth=2)
        )
        title = "dot product"
        annotation = (
            f"{vectors[0].name} . {vectors[1].name} = {dot_value:.6g}\n"
            f"angle = {angle:.3f} deg   |a| = {norm_first:.4g}   |b| = {norm_second:.4g}"
        )
    elif operation == "cross":
        if dimension != 3:
            raise SolveError("The cross product needs two 3D vectors")
        result = np.cross(first, second)
        _quiver(ax, first, "#1f77b4", vectors[0].name)
        _quiver(ax, second, "#ff7f0e", vectors[1].name)
        _quiver(ax, result, "#2ca02c", f"{vectors[0].name}x{vectors[1].name}")
        title = "cross product"
        annotation = (
            f"{vectors[0].name} x {vectors[1].name} = {np.array2string(result, precision=4)}"
        )
    else:
        raise SolveError(f"Unknown vector operation {operation!r}")

    magnitudes = np.abs(np.concatenate([first, second]))
    limit = 1.5 * float(magnitudes.max()) if magnitudes.size else 1.5
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.set_title(title)
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
        parameters=[ParamSpec(name="scale", default=float(scale), min=-5.0, max=5.0, step=0.1)],
        meta={
            "kind": "vectors",
            "operation": operation,
            "vectors": [vector.name for vector in vectors],
            "annotation": annotation,
            "warnings": [],
        },
    )


# --------------------------------------------------------------------- matrices
def as_matrix(values: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    """Validate and return a square matrix as a float array."""
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ParseError("The matrix must be square (2x2 or 3x3)")
    if matrix.shape[0] not in (2, 3):
        raise ParseError("Only 2x2 and 3x3 matrices are supported")
    return matrix


def parse_matrix(text: str) -> np.ndarray:
    """Parse ``[[1,2],[3,4]]`` into a NumPy array."""
    cleaned = text.strip()
    if cleaned.startswith("[[") and cleaned.endswith("]]"):
        cleaned = cleaned[2:-2]
    rows = [row.strip() for row in cleaned.split("],[")] if "]," in cleaned else None
    if rows is None:
        rows = []
        for chunk in re.split(r"\]\s*\[", cleaned.strip("[]")):
            rows.append(chunk)
    matrix: list[list[float]] = []
    for row in rows:
        parts = [part.strip() for part in row.split(",") if part.strip()]
        try:
            matrix.append([float(part) for part in parts])
        except ValueError as exc:
            raise ParseError(f"Could not read the matrix row {row!r}") from exc
    if not matrix:
        raise ParseError("The matrix is empty")
    return as_matrix(matrix)


def transform_matrix(
    matrix: np.ndarray | None = None,
    rotation: float = 0.0,
    shear: float = 0.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    reflect: bool = False,
) -> np.ndarray:
    """Build the transformation matrix from the preset controls."""
    if matrix is not None:
        return as_matrix(matrix)
    angle = math.radians(rotation)
    rotation_matrix = np.array(
        [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
    )
    transform = np.array([[scale_x, shear], [0.0, scale_y]])
    if reflect:
        transform = transform @ np.array([[-1.0, 0.0], [0.0, 1.0]])
    return rotation_matrix @ transform


def _transformed_grid(matrix: np.ndarray, lines: int = GRID_LINES) -> list[list[np.ndarray]]:
    """The transformed grid lines (one list per direction)."""
    span = 1.0
    coordinates = np.linspace(-span, span, lines)
    vertical: list[np.ndarray] = []
    horizontal: list[np.ndarray] = []
    for value in coordinates:
        start = np.array([value, -span])
        end = np.array([value, span])
        vertical.append(np.array([matrix @ start, matrix @ end]))
        start = np.array([-span, value])
        end = np.array([span, value])
        horizontal.append(np.array([matrix @ start, matrix @ end]))
    return vertical + horizontal


def matrix_view(
    matrix: np.ndarray | None = None,
    rotation: float = 0.0,
    shear: float = 0.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    reflect: bool = False,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Show what a 2x2 matrix does to the plane (grid warping)."""
    transform = transform_matrix(matrix, rotation, shear, scale_x, scale_y, reflect)
    determinant = float(np.linalg.det(transform))

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.axhline(0, color="0.4", linewidth=0.9)
    ax.axvline(0, color="0.4", linewidth=0.9)
    ax.grid(True, alpha=0.2)

    for segment in _transformed_grid(transform):
        ax.plot(segment[:, 0], segment[:, 1], color="#1f77b4", linewidth=1.0, alpha=0.8)
    for value in np.linspace(-1.0, 1.0, GRID_LINES):
        ax.plot([-1.0, 1.0], [value, value], color="0.75", linewidth=0.6)
        ax.plot([value, value], [-1.0, 1.0], color="0.75", linewidth=0.6)

    square = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    transformed = square @ transform.T
    ax.add_patch(
        Polygon(
            square, closed=True, facecolor="none", edgecolor="0.55", linestyle="--", linewidth=1.4
        )
    )
    ax.add_patch(
        Polygon(
            transformed,
            closed=True,
            facecolor="#ff7f0e",
            edgecolor="#b35c00",
            alpha=0.35,
            linewidth=1.8,
        )
    )

    basis_i = transform @ np.array([1.0, 0.0])
    basis_j = transform @ np.array([0.0, 1.0])
    _quiver(ax, basis_i, "#2ca02c", "T(i)")
    _quiver(ax, basis_j, "#d62728", "T(j)")

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("matrix transformation")
    ax.text(
        0.03,
        0.97,
        f"M = {np.array2string(transform, precision=3)}\n"
        f"det(M) = {determinant:.6g}   (area scale)",
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
            ParamSpec(name="rotation", default=float(rotation), min=-180.0, max=180.0, step=1.0),
            ParamSpec(name="shear", default=float(shear), min=-2.0, max=2.0, step=0.05),
            ParamSpec(name="scale_x", default=float(scale_x), min=-3.0, max=3.0, step=0.05),
            ParamSpec(name="scale_y", default=float(scale_y), min=-3.0, max=3.0, step=0.05),
        ],
        meta={
            "kind": "matrix",
            "matrix": transform.tolist(),
            "determinant": determinant,
            "rotation": rotation,
            "shear": shear,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "reflect": reflect,
            "warnings": [],
        },
    )


# --------------------------------------------------------------------- eigen
def eigen_values(matrix: np.ndarray) -> tuple[list[complex], list[np.ndarray]]:
    """The eigen values and eigen vectors of a square matrix."""
    values, vectors = np.linalg.eig(np.asarray(matrix, dtype=float))
    return [complex(value) for value in values], [
        np.real(vectors[:, index]) for index in range(vectors.shape[1])
    ]


def exact_eigen_values(matrix: np.ndarray) -> list[sympy.Basic] | None:
    """The exact eigen values computed by SymPy (for small matrices)."""
    try:
        sympy_matrix = sympy.Matrix(np.asarray(matrix, dtype=float).tolist())
        return [value for value, _multiplicity, _vectors in sympy_matrix.eigenvects()]
    except Exception:  # noqa: BLE001 - SymPy may fail on ugly matrices
        return None


def eigen_view(
    matrix: np.ndarray | None = None,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Visualise the eigen structure of a 2x2 matrix."""
    transform = as_matrix(matrix)
    values, vectors = eigen_values(transform)
    exact = exact_eigen_values(transform)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.axhline(0, color="0.4", linewidth=0.9)
    ax.axvline(0, color="0.4", linewidth=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("eigen values and eigen vectors")

    # the unit square before and after
    square = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    transformed = square @ transform.T
    ax.add_patch(
        Polygon(
            square, closed=True, facecolor="none", edgecolor="0.6", linestyle="--", linewidth=1.3
        )
    )
    ax.add_patch(
        Polygon(
            transformed,
            closed=True,
            facecolor="#ff7f0e",
            edgecolor="#b35c00",
            alpha=0.3,
            linewidth=1.6,
        )
    )

    warnings: list[str] = []
    complex_values = [value for value in values if abs(value.imag) > 1e-9]
    if complex_values:
        warnings.append(
            "The matrix has complex eigen values "
            + ", ".join(f"{value}" for value in complex_values)
            + " - there is no real eigen vector to draw."
        )

    real_index = 0
    for value, vector in zip(values, vectors, strict=False):
        if abs(value.imag) > 1e-9:
            continue
        norm = float(np.linalg.norm(vector))
        if norm < 1e-12:
            continue
        direction = vector / norm
        length = float(abs(value.real)) or 1.0
        _quiver(ax, direction * length, "#2ca02c", f"v (lambda = {value.real:.4g})")
        # the image of the eigen vector stays on the same line
        image = transform @ (direction * length)
        _quiver(ax, image, "#d62728", "M v")
        real_index += 1

    annotations = []
    for value in values:
        if abs(value.imag) > 1e-9:
            annotations.append(f"lambda = {value.real:.6g} {value.imag:+.6g}i")
        else:
            annotations.append(f"lambda = {value.real:.6g}")
    if exact:
        annotations.append("exact: " + ", ".join(sympy.latex(value) for value in exact))

    ax.text(
        0.03,
        0.97,
        "\n".join(annotations),
        transform=ax.transAxes,
        fontsize=10,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
    )
    fig.subplots_adjust(left=0.14, right=0.95, top=0.90, bottom=0.12)

    return VisualizationResult(
        figure=fig,
        parameters=[],
        meta={
            "kind": "eigen",
            "matrix": transform.tolist(),
            "eigenvalues": [str(value) for value in values],
            "exact_eigenvalues": [sympy.latex(value) for value in exact] if exact else [],
            "real_eigenvectors": real_index,
            "determinant": float(np.linalg.det(transform)),
            "warnings": warnings,
        },
    )


# --------------------------------------------------------------- linear systems
def parse_system(text: str) -> list[sympy.Equality]:
    """Parse ``2x+y=5; x-y=1`` into equations."""
    from aieva.core.safe_parse import parse_equation

    if not text or not text.strip():
        raise ParseError("No system given")
    equations = []
    for chunk in re.split(r"[;\n]", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        equations.append(parse_equation(chunk))
    if not equations:
        raise ParseError("No equation found")
    return equations


def solve_system(equations: Sequence[sympy.Equality]) -> dict[str, Any]:
    """Solve a linear system and describe the solution set."""
    variables = sorted(
        {symbol for equation in equations for symbol in equation.free_symbols},
        key=lambda item: item.name,
    )
    if not variables:
        raise SolveError("The system does not contain any variable")
    matrix, vector = sympy.linear_eq_to_matrix(equations, variables)
    solution_set = sympy.linsolve((matrix, vector), variables)
    solutions = list(solution_set)
    free = set(solution_set.free_symbols)

    if not solutions:
        return {
            "type": "none",
            "variables": [str(variable) for variable in variables],
            "solutions": [],
            "explanation": "The equations are contradictory - there is no solution.",
            "warnings": [],
        }
    if len(solutions) > 1 or free:
        return {
            "type": "infinite",
            "variables": [str(variable) for variable in variables],
            "solutions": [str(item) for item in solutions],
            "explanation": "The equations describe a line (or a plane) - infinitely many solutions.",
            "warnings": [],
        }
    point = solutions[0]
    numeric = []
    for value in point:
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            numeric.append(float("nan"))
    return {
        "type": "unique",
        "variables": [str(variable) for variable in variables],
        "solutions": [str(item) for item in solutions],
        "point": numeric,
        "explanation": "The system has exactly one solution.",
        "warnings": [],
    }


def system_view(
    equations: Sequence[sympy.Equality] | str,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Plot the equations of a linear system and mark the solution."""
    if isinstance(equations, str):
        equations = parse_system(equations)
    equations = list(equations)
    solution = solve_system(equations)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.axhline(0, color="0.4", linewidth=0.9)
    ax.axvline(0, color="0.4", linewidth=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("system of linear equations")

    variables = solution["variables"]
    if len(variables) == 2:
        xs = np.linspace(-10.0, 10.0, 400)
        colours = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
        for index, equation in enumerate(equations):
            x_symbol, y_symbol = sympy.symbols(variables[0]), sympy.symbols(variables[1])
            expression = sympy.solve(equation, y_symbol)
            if not expression:
                continue
            func = sympy.lambdify(x_symbol, expression[0], modules=["numpy"])
            with np.errstate(all="ignore"):
                ys = np.asarray(func(xs), dtype=float)
            ys = np.where(np.abs(ys) > 1e6, np.nan, ys)
            ax.plot(
                xs,
                ys,
                color=colours[index % len(colours)],
                linewidth=2.0,
                label=f"{sympy.latex(equation)}",
            )
        if solution["type"] == "unique":
            point = solution["point"]
            ax.plot(point[0], point[1], "o", color="#d62728", markersize=10, zorder=5)
            ax.annotate(
                f"({point[0]:.4g}, {point[1]:.4g})",
                (point[0], point[1]),
                textcoords="offset points",
                xytext=(10, 10),
                color="#d62728",
                fontweight="bold",
            )
        ax.legend(loc="best", fontsize=9)
    else:
        ax.text(
            0.5,
            0.5,
            "Only two variable systems are drawn",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=theme_muted(),
        )

    ax.text(
        0.03,
        0.97,
        solution["explanation"],
        transform=ax.transAxes,
        fontsize=10,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
    )
    fig.tight_layout()

    return VisualizationResult(
        figure=fig,
        parameters=[],
        meta={
            "kind": "system",
            "solution_type": solution["type"],
            "solutions": solution["solutions"],
            "point": solution.get("point"),
            "variables": solution["variables"],
            "explanation": solution["explanation"],
            "warnings": solution["warnings"],
        },
    )


def theme_muted() -> tuple[float, float, float, float]:
    """The muted text colour (kept here to avoid a UI import in the core)."""
    return (0.45, 0.48, 0.55, 1)


# ------------------------------------------------------------------- 3D helpers
def cube_view(
    matrix: np.ndarray | None = None,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> VisualizationResult:
    """Transform the unit cube with a 3x3 matrix."""
    transform = as_matrix(matrix)
    if transform.shape != (3, 3):
        raise ParseError("The cube view needs a 3x3 matrix")

    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    corners = np.array([[x, y, z] for x in (0.0, 1.0) for y in (0.0, 1.0) for z in (0.0, 1.0)])
    faces = [
        [0, 1, 3, 2],
        [4, 5, 7, 6],
        [0, 1, 5, 4],
        [2, 3, 7, 6],
        [0, 2, 6, 4],
        [1, 3, 7, 5],
    ]
    transformed = corners @ transform.T

    fig = plt.figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    for face in faces:
        polygon = Poly3DCollection(
            [transformed[face]], facecolor="#ff7f0e", edgecolor="#b35c00", alpha=0.35
        )
        ax.add_collection3d(polygon)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.set_title("3x3 matrix applied to the unit cube")
    ax.text2D(
        0.03,
        0.97,
        f"M = {np.array2string(transform, precision=3)}\n"
        f"det(M) = {float(np.linalg.det(transform)):.6g}",
        transform=ax.transAxes,
        fontsize=10,
        va="top",
        ha="left",
    )
    fig.tight_layout()

    return VisualizationResult(
        figure=fig,
        parameters=[],
        meta={
            "kind": "cube",
            "matrix": transform.tolist(),
            "determinant": float(np.linalg.det(transform)),
            "warnings": [],
        },
    )


__all__ = [
    "GRID_LINES",
    "VectorSpec",
    "as_matrix",
    "cube_view",
    "eigen_values",
    "eigen_view",
    "exact_eigen_values",
    "matrix_view",
    "parse_matrix",
    "parse_system",
    "parse_vectors",
    "solve_system",
    "system_view",
    "transform_matrix",
    "vector_view",
]
