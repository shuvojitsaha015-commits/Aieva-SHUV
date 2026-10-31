"""The template of a subject plugin - copy it and fill it in.

This directory starts with an underscore, so the plugin registry **ignores**
it (see :meth:`aieva.core.plugin_registry.PluginRegistry.discover`). It is
the starting point for a new subject:

.. code-block:: bash

    cp -r aieva/plugins/_template_plugin aieva/plugins/biology
    # then rename the class, the name and the description

After that the subject appears in the UI by itself - the home screen is built
from the metadata of the registry, so **no core file has to be changed**.

The rules for every plugin:

* **no Kivy import** - the plugin is headless and testable;
* only the shared services of :mod:`aieva.core` are used (the safe parser,
  the LaTeX adapter, the cache, the models);
* the maths of the subject is done with SymPy / NumPy / Matplotlib;
* the result is a :class:`~aieva.core.models.VisualizationResult` (a figure
  and the parameters for the sliders) or a
  :class:`~aieva.core.models.SolveResult` (the answer and the steps).

The full walk-through is in ``docs/ADDING_A_SUBJECT.md``.
"""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from aieva.core.errors import ParseError
from aieva.core.models import ParsedInput, SolveResult, Step, VisualizationResult
from aieva.core.plugin_base import SubjectPlugin


class TemplatePlugin(SubjectPlugin):
    """A minimal subject plugin - the three steps of every plugin.

    * ``parse`` normalises the input (the text of the teacher, the LaTeX of
      the board or the answer of the OCR),
    * ``solve`` returns the answer with the steps,
    * ``visualize`` returns the picture and the parameters of the sliders.
    """

    #: The unique name of the subject - it is the key of the registry.
    name = "template"

    #: What the teacher sees on the subject button.
    display_name = "Template"

    #: One line under the name.
    description = "A documented example of a subject plugin."

    #: The optional packages the plugin needs (they are checked at the start).
    requires: tuple[str, ...] = ()

    #: Hints for the UI layer.
    ui_hints = {"viewer": "matplotlib", "editor": "text"}

    #: The order in the subject list (the mathematics is 10).
    order = 900

    # ------------------------------------------------------------------ parse
    def parse(self, parsed_input: ParsedInput) -> ParsedInput:
        """Read the number out of the input (the smallest useful example)."""
        raw = (parsed_input.raw or "").strip()
        if not raw:
            raise ParseError("Nothing to parse")
        try:
            value = float(raw.split()[0].replace(",", "."))
        except (ValueError, IndexError) as exc:
            raise ParseError(f"I could not read a number in {raw!r}") from exc
        parsed_input.sympy_expr = value
        return parsed_input

    # ------------------------------------------------------------------ solve
    def solve(self, parsed_input: ParsedInput) -> SolveResult:
        """Return the answer and the steps of the solution."""
        if parsed_input.sympy_expr is None:
            parsed_input = self.parse(parsed_input)
        value = float(parsed_input.sympy_expr)  # type: ignore[arg-type]
        return SolveResult(
            problem_type="template_value",
            answer_text=f"{value:g}",
            answer_latex=f"{value:g}",
            steps=[
                Step(
                    title="Read the value",
                    explanation="The plugin reads the number out of the input.",
                    latex=f"{value:g}",
                )
            ],
        )

    # ------------------------------------------------------------- visualize
    def visualize(self, parsed_input: ParsedInput, **opts: Any) -> VisualizationResult:
        """Draw the value (the smallest useful picture)."""
        if parsed_input.sympy_expr is None:
            parsed_input = self.parse(parsed_input)
        value = float(parsed_input.sympy_expr)  # type: ignore[arg-type]

        figure, axes = plt.subplots(figsize=(6.0, 4.0), dpi=100)
        x = np.linspace(-5.0, 5.0, 100)
        axes.plot(x, value * np.ones_like(x), color="#1f77b4", linewidth=2.5)
        axes.set_title(f"the value is {value:g}")
        axes.set_xlabel("x")
        axes.set_ylabel("y")
        axes.grid(True, alpha=0.3)
        figure.subplots_adjust(left=0.12, right=0.96, top=0.90, bottom=0.12)

        return VisualizationResult(
            figure=figure,
            parameters=[],
            meta={"kind": "template", "value": value},
        )

    # ---------------------------------------------------------- capabilities
    def capabilities(self) -> list[str]:
        """The features the UI may offer for this subject."""
        return ["parse", "solve", "visualize"]


__all__ = ["TemplatePlugin"]
