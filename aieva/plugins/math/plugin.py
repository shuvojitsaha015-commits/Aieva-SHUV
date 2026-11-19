"""The mathematics subject plugin.

This is the only plugin shipped in v1. It wires the shared services (safe
parser, LaTeX adapter, cache) to the maths specific engines:

* :mod:`aieva.plugins.math.equations` - equation analysis and plotting (1.a)
* :mod:`aieva.plugins.math.calculus` - calculus visualisations (1.b)
* :mod:`aieva.plugins.math.linalg` - vectors / matrices / eigen values (1.c)
* :mod:`aieva.plugins.math.complexnum` - Argand diagram (1.c)
* :mod:`aieva.plugins.math.plot3d` - 2D / 3D plots (1.d)
* :mod:`aieva.plugins.math.solver` - solving and step by step steps (1.e)
* :mod:`aieva.plugins.math.wordproblems` - word problems (1.f)

The plugin never imports Kivy - the UI calls into it.
"""

from __future__ import annotations

from typing import Any

import sympy

from aieva.core.errors import ParseError
from aieva.core.latex_adapter import latex_to_equation, latex_to_sympy
from aieva.core.models import ParsedInput, SolveResult, VisualizationResult
from aieva.core.plugin_base import SubjectPlugin
from aieva.core.safe_parse import parse_equation, parse_text_expression


class MathPlugin(SubjectPlugin):
    """Mathematics: parse, solve and visualise."""

    name = "math"
    display_name = "Mathematics"
    description = "Equations, calculus, linear algebra, complex numbers, word problems."
    #: SymPy / NumPy / Matplotlib are part of the core install - no extras needed.
    requires: tuple[str, ...] = ()
    ui_hints = {"viewer": "matplotlib", "editor": "text"}
    order = 10

    # ------------------------------------------------------------------ parse
    def parse(self, parsed_input: ParsedInput) -> ParsedInput:
        """Normalise raw text / LaTeX into a SymPy expression.

        ``ParsedInput.kind`` decides which parser is used:

        * ``"latex"``  -> :func:`latex_to_sympy` / :func:`latex_to_equation`
        * everything else -> :func:`parse_text_expression` / :func:`parse_equation`
        """
        raw = parsed_input.raw or ""
        if not raw.strip():
            raise ParseError("Nothing to parse")

        if parsed_input.kind == "latex":
            if "=" in raw:
                expression = latex_to_equation(raw)
            else:
                expression = latex_to_sympy(raw)
        else:
            if "=" in raw:
                expression = parse_equation(raw)
            else:
                expression = parse_text_expression(raw)

        parsed_input.sympy_expr = expression
        if parsed_input.kind == "latex" and parsed_input.latex is None:
            parsed_input.latex = raw
        return parsed_input

    # ------------------------------------------------------------------ solve
    def solve(self, parsed_input: ParsedInput) -> SolveResult:
        """Solve the problem (implemented in Phase 8)."""
        from aieva.plugins.math.solver import solve_parsed

        if parsed_input.sympy_expr is None:
            parsed_input = self.parse(parsed_input)
        return solve_parsed(parsed_input)

    # ------------------------------------------------------------- visualize
    def visualize(self, parsed_input: ParsedInput, **opts: Any) -> VisualizationResult:
        """Produce a figure for the parsed problem.

        A table of values is drawn as a chart - the renderer is in the core,
        so physics and chemistry can draw their tables the same way.
        """
        from aieva.plugins.math.equations import visualize_parsed

        # a table of values is not an expression - it is looked for first
        chart = self._chart_of(parsed_input)
        if chart is not None:
            return chart
        if parsed_input.sympy_expr is None:
            parsed_input = self.parse(parsed_input)
        return visualize_parsed(parsed_input, **opts)

    @staticmethod
    def _chart_of(parsed_input: ParsedInput) -> Any:
        """The chart of a table (``None`` when the input is not a table)."""
        raw = str(getattr(parsed_input, "raw", "") or "")
        if not raw:
            return None
        from aieva.core.charts import chart_figure, parse_table

        data = parse_table(raw)
        if data is None:
            return None
        try:
            figure = chart_figure(data)
        except ValueError:
            return None
        from aieva.core.models import VisualizationResult

        return VisualizationResult(
            figure=figure,
            parameters=[],
            meta={"kind": "chart", "chart_kind": data.kind, "title": data.title},
        )

    def create_session(self, parsed_input: ParsedInput, **opts: Any) -> Any:
        """Return a :class:`~aieva.plugins.math.equations.PlotSession`."""
        from aieva.plugins.math.equations import build_session

        if parsed_input.sympy_expr is None:
            parsed_input = self.parse(parsed_input)
        return build_session(parsed_input, **opts)

    # ---------------------------------------------------------- capabilities
    def capabilities(self) -> list[str]:
        """The features that are available in this build."""
        return [
            "parse",
            "equation_plot",
            "calculus",
            "linear_algebra",
            "complex_numbers",
            "solve",
            "visualize",
        ]

    # ------------------------------------------------------------- utilities
    @staticmethod
    def to_symbols(expression: Any) -> list[sympy.Symbol]:
        """All free symbols of an expression, sorted by name."""
        if expression is None:
            return []
        return sorted(expression.free_symbols, key=lambda s: s.name)


__all__ = ["MathPlugin"]
