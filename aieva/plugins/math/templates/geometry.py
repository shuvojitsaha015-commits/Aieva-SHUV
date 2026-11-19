"""The geometry template: a shape with labelled dimensions.

The model gives the shape (``rectangle``, ``circle``, ``triangle`` or
``right_triangle``) and its dimensions. The figure draws the shape with the
measurements written next to the sides and the area (and the perimeter) in the
title.
"""

from __future__ import annotations

import math
from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

from aieva.core.errors import SolveError  # noqa: E402
from aieva.core.models import Step, VisualizationResult  # noqa: E402
from aieva.core.plotting import new_subplots  # noqa: E402

#: The shapes that the template understands.
SHAPES = ("rectangle", "circle", "triangle", "right_triangle")


def _shape(problem: Any) -> str:
    """Which shape is it?"""
    for shape in SHAPES:
        if shape in problem.problem_type or shape in problem.visualization_hint.lower():
            return shape
    return "rectangle"


def solve(problem: Any) -> Any:
    """Compute the area and the perimeter of the shape."""
    from aieva.plugins.math.wordproblems import WordProblemSolution

    shape = _shape(problem)
    if shape == "circle":
        radius = problem.number("r")
        if radius <= 0:
            raise SolveError("The radius has to be positive")
        area = math.pi * radius**2
        perimeter = 2 * math.pi * radius
        steps = [
            Step(
                title="The area of a circle",
                explanation="A = pi * r^2",
                latex=f"A = \\pi r^2 = {area:.4g}",
            ),
            Step(
                title="The circumference",
                explanation="C = 2 * pi * r",
                latex=f"C = 2\\pi r = {perimeter:.4g}",
            ),
        ]
    elif shape in ("triangle", "right_triangle"):
        first = problem.number("a")
        second = problem.number("b")
        area = first * second / 2.0
        if shape == "right_triangle":
            perimeter = first + second + math.hypot(first, second)
            steps = [
                Step(
                    title="The hypotenuse",
                    explanation="The Pythagoras theorem",
                    latex=f"c = \\sqrt{{{first:g}^2 + {second:g}^2}} = {math.hypot(first, second):.4g}",
                ),
                Step(
                    title="The area",
                    explanation="A = a * b / 2",
                    latex=f"A = \\frac{{{first:g} \\cdot {second:g}}}{{2}} = {area:.4g}",
                ),
            ]
        else:
            perimeter = first + second + math.hypot(first, second)
            steps = [
                Step(
                    title="The area",
                    explanation="A = a * b / 2",
                    latex=f"A = \\frac{{{first:g} \\cdot {second:g}}}{{2}} = {area:.4g}",
                ),
            ]
    else:
        width = problem.number("w")
        height = problem.number("h")
        area = width * height
        perimeter = 2 * (width + height)
        steps = [
            Step(
                title="The area",
                explanation="A = w * h",
                latex=f"A = {width:g} \\cdot {height:g} = {area:.4g}",
            ),
            Step(
                title="The perimeter",
                explanation="U = 2 * (w + h)",
                latex=f"U = 2({width:g} + {height:g}) = {perimeter:.4g}",
            ),
        ]

    return WordProblemSolution(
        values={"area": area, "perimeter": perimeter},
        latex={"area": f"A = {area:.4g}", "perimeter": f"U = {perimeter:.4g}"},
        steps=steps,
    )


def render(problem: Any, solution: Any) -> VisualizationResult:
    """Draw the shape with its dimensions."""
    shape = _shape(problem)
    area = solution.values["area"]
    perimeter = solution.values["perimeter"]

    fig, ax = new_subplots(figsize=(6.5, 5.5), dpi=100)
    ax.set_aspect("equal", adjustable="box")

    if shape == "circle":
        radius = problem.number("r")
        ax.add_patch(Circle((0, 0), radius, fill=False, edgecolor="#1f77b4", linewidth=2.5))
        ax.plot([0, radius], [0, 0], color="#d62728", linewidth=2)
        ax.plot([0], [0], "o", color="#444444", markersize=5)
        ax.text(
            radius / 2,
            radius * 0.08,
            f"r = {radius:g} {problem.unit('r')}",
            color="#d62728",
            fontsize=12,
        )
        ax.set_xlim(-radius * 1.4, radius * 1.4)
        ax.set_ylim(-radius * 1.4, radius * 1.4)
    elif shape in ("triangle", "right_triangle"):
        first = problem.number("a")
        second = problem.number("b")
        points = [(0, 0), (first, 0), (0, second)]
        ax.add_patch(Polygon(points, closed=True, fill=False, edgecolor="#1f77b4", linewidth=2.5))
        ax.plot([0, first], [0, 0], color="#d62728", linewidth=2)
        ax.plot([0, 0], [0, second], color="#2ca02c", linewidth=2)
        ax.text(first / 2, -second * 0.08, f"a = {first:g}", color="#d62728", fontsize=12)
        ax.text(-first * 0.12, second / 2, f"b = {second:g}", color="#2ca02c", fontsize=12)
        ax.set_xlim(-first * 0.35, first * 1.2)
        ax.set_ylim(-second * 0.25, second * 1.2)
    else:
        width = problem.number("w")
        height = problem.number("h")
        ax.add_patch(
            Rectangle((0, 0), width, height, fill=False, edgecolor="#1f77b4", linewidth=2.5)
        )
        ax.plot([0, width], [0, 0], color="#d62728", linewidth=2)
        ax.plot([0, 0], [0, height], color="#2ca02c", linewidth=2)
        ax.text(
            width / 2,
            -height * 0.09,
            f"w = {width:g} {problem.unit('w')}",
            color="#d62728",
            fontsize=12,
        )
        ax.text(
            -width * 0.16,
            height / 2,
            f"h = {height:g} {problem.unit('h')}",
            color="#2ca02c",
            fontsize=12,
        )
        ax.set_xlim(-width * 0.35, width * 1.2)
        ax.set_ylim(-height * 0.25, height * 1.2)

    ax.set_title(f"{shape.replace('_', ' ')}: area = {area:.4g}, perimeter = {perimeter:.4g}")
    ax.grid(True, alpha=0.25)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.subplots_adjust(left=0.08, right=0.96, top=0.90, bottom=0.08)

    return VisualizationResult(
        figure=fig,
        parameters=[],
        meta={
            "kind": "word_problem",
            "template": "geometry",
            "shape": shape,
            "area": area,
            "perimeter": perimeter,
            "warnings": [],
        },
    )


__all__ = ["SHAPES", "render", "solve"]
