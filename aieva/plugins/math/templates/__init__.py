"""The four word problem templates of Aieva v1.

The scope is fixed (see the plan): **kinematic** (a projectile and a uniform
motion), **optimisation**, **rate** and **geometry**. Every template offers
the same two functions:

``solve(problem) -> WordProblemSolution``
    the maths, done with SymPy;

``render(problem, solution) -> VisualizationResult``
    the picture.

A new template is one more module in this package plus one line in
:data:`TEMPLATES` - nothing else in the code base changes.
"""

from __future__ import annotations

from types import ModuleType

from aieva.core.errors import SolveError

#: The problem types of v1 and the template that draws them.
TEMPLATES: dict[str, str] = {
    "kinematic_projectile": "aieva.plugins.math.templates.kinematic",
    "uniform_motion": "aieva.plugins.math.templates.kinematic",
    "optimization": "aieva.plugins.math.templates.optimization",
    "rate_tank": "aieva.plugins.math.templates.rate",
    "geometry": "aieva.plugins.math.templates.geometry",
}

#: The four categories of the plan.
CATEGORIES: tuple[str, ...] = ("kinematic", "optimization", "rate", "geometry")


def get_template(problem_type: str) -> ModuleType:
    """The template module of a problem type."""
    import importlib

    module_name = TEMPLATES.get(problem_type)
    if module_name is None:
        raise SolveError(
            f"There is no template for {problem_type!r} - " f"known: {', '.join(sorted(TEMPLATES))}"
        )
    return importlib.import_module(module_name)


__all__ = ["CATEGORIES", "TEMPLATES", "get_template"]
