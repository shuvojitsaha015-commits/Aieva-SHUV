"""The optimisation template: maximise (or minimise) something under a constraint.

The model gives the objective as a polynomial of one variable (the classic
fence / box / area problems) and the interval in which the variable lives.
The extremum is found with SymPy (the derivative), the result is marked in
the figure.
"""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

import numpy as np  # noqa: E402
import sympy  # noqa: E402

from aieva.core.errors import SolveError  # noqa: E402
from aieva.core.models import ParamSpec, Step, VisualizationResult  # noqa: E402
from aieva.core.plotting import new_subplots  # noqa: E402


def _objective(problem: Any) -> sympy.Expr:
    """The objective function of the model."""
    from aieva.core.safe_parse import parse_text_expression

    variable = sympy.Symbol("x")
    known = problem.symbols()
    for equation in problem.equations:
        left, _, right = equation.partition("=")
        for candidate in (right, left):
            if not candidate.strip():
                continue
            try:
                expression = parse_text_expression(candidate)
            except Exception:  # noqa: BLE001 - the LLM may write anything
                continue
            if variable not in expression.free_symbols:
                continue
            if known:
                # the values of the model (the fence length, the price, ...)
                expression = expression.subs(
                    {
                        sympy.Symbol(name): value
                        for name, value in known.items()
                        if name != "x" and sympy.Symbol(name) in expression.free_symbols
                    }
                )
            return expression
    raise SolveError("The model does not contain an objective function for x")


def solve(problem: Any) -> Any:
    """Find the extremum of the objective inside the interval."""
    from aieva.plugins.math.wordproblems import WordProblemSolution

    variable = sympy.Symbol("x")
    objective = _objective(problem)
    low = problem.value("x_min", 0.0)
    high = problem.value("x_max", 0.0)
    if high <= low:
        raise SolveError("The interval of the constraint is empty")

    derivative = sympy.diff(objective, variable)
    critical = [value for value in sympy.solve(derivative, variable) if value.is_real]
    candidates = [value for value in critical if low <= float(value) <= high]
    for bound in (low, high):
        candidates.append(sympy.Float(bound))

    def objective_value(point: sympy.Expr) -> float:
        return float(objective.subs(variable, point).evalf())

    best = max(candidates, key=objective_value)
    best_value = objective_value(best)

    steps = [
        Step(
            title="The objective",
            explanation="This is the quantity that has to be as large (or small) as possible.",
            latex=sympy.latex(objective),
        ),
        Step(
            title="The derivative",
            explanation="The extremum is where the derivative is zero.",
            latex=sympy.latex(derivative) + " = 0",
        ),
        Step(
            title="The extremum",
            explanation=(
                f"In the interval [{low:g}, {high:g}] the best value is at x = {float(best):.4g}."
            ),
            latex=sympy.latex(objective.subs(variable, best)) + f" = {best_value:.4g}",
        ),
    ]
    return WordProblemSolution(
        values={"x": float(best), "objective": best_value},
        latex={
            "x": f"x = {float(best):.4g}",
            "objective": sympy.latex(objective.subs(variable, best)) + f" = {best_value:.4g}",
        },
        steps=steps,
    )


def render(problem: Any, solution: Any) -> VisualizationResult:
    """Draw the objective with the constraint and the marked extremum."""
    variable = sympy.Symbol("x")
    objective = _objective(problem)
    low = problem.value("x_min", 0.0)
    high = problem.value("x_max", 0.0)

    values = np.linspace(low, high, 400)
    function = sympy.lambdify(variable, objective, modules=["numpy"])
    with np.errstate(all="ignore"):
        numbers = np.asarray(function(values), dtype=float)

    best_x = solution.values["x"]
    best_value = solution.values["objective"]

    fig, ax = new_subplots(figsize=(7.5, 5.5), dpi=100)
    ax.plot(values, numbers, color="#1f77b4", linewidth=2.5, label="objective")
    ax.axvspan(low, high, color="#4080f0", alpha=0.08, label="the constraint")
    ax.plot([best_x], [best_value], "*", color="#2ca02c", markersize=17, zorder=5)
    ax.annotate(
        f"maximum: {best_value:.4g}\nat x = {best_x:.4g}",
        xy=(best_x, best_value),
        xytext=(low + (high - low) * 0.04, best_value * 0.35),
        color="#2ca02c",
        fontsize=11,
        arrowprops={"arrowstyle": "->", "color": "#2ca02c"},
    )
    ax.set_xlabel(problem.unit("x") or "x")
    ax.set_ylabel("objective")
    ax.set_title("optimisation")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=9)
    fig.subplots_adjust(left=0.12, right=0.96, top=0.92, bottom=0.10)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name="x_min", default=low, min=low, max=high, step=0.1),
            ParamSpec(name="x_max", default=high, min=low, max=high, step=0.1),
        ],
        meta={
            "kind": "word_problem",
            "template": "optimization",
            "x": best_x,
            "objective": best_value,
            "warnings": [],
        },
    )


__all__ = ["render", "solve"]
