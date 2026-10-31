"""Word problems: the structured model, the solution and the visualisation.

The LLM (through the server) turns a word problem into a **structured model**
- variables, equations, unknowns. This module

* validates that model (the LLM output is untrusted),
* solves it with SymPy,
* checks the result (sanity checks) and
* hands it to one of the four template visualisers.

The templates are deliberately fixed (see the plan): kinematic (projectile and
uniform motion), optimisation, rate and geometry.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import sympy

from aieva.core.errors import ParseError, SolveError
from aieva.core.models import ParamSpec, Step, VisualizationResult

LOGGER = logging.getLogger(__name__)

#: The problem types that v1 can visualise.
SUPPORTED_TYPES: tuple[str, ...] = (
    "kinematic_projectile",
    "uniform_motion",
    "optimization",
    "rate_tank",
    "geometry",
)

#: The problem types that the schema knows but v1 does not draw.
KNOWN_BUT_UNSUPPORTED: tuple[str, ...] = ("mixture", "unsupported")

#: ``g = 9.8 m/s^2`` and friends.
_ASSUMPTION_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(-?[0-9.]+)")


def _text_list(value: Any) -> list[str]:
    """A list of strings - everything else is dropped (the LLM is untrusted)."""
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


@dataclass
class ProblemVariable:
    """One variable of a word problem."""

    name: str
    description: str = ""
    value: float | None = None
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "value": self.value,
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ProblemVariable:
        value = data.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float, type(None))):
            value = None
        return cls(
            name=str(data.get("name", "")).strip(),
            description=str(data.get("description", "")).strip(),
            value=float(value) if value is not None else None,
            unit=str(data.get("unit", "")).strip(),
        )


@dataclass
class WordProblem:
    """The structured model of a word problem."""

    problem_type: str = "unsupported"
    variables: list[ProblemVariable] = field(default_factory=list)
    equations: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    visualization_hint: str = ""
    parameters_for_sliders: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    source_text: str = ""

    # ------------------------------------------------------------------ api
    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WordProblem:
        """Build the model from the answer of the LLM (validated!)."""
        if not isinstance(data, Mapping):
            raise ParseError("The word problem model is not an object")
        problem_type = str(data.get("problem_type", "unsupported")).strip()
        variables = [
            ProblemVariable.from_dict(item)
            for item in data.get("variables") or []
            if isinstance(item, Mapping)
        ]
        variables = [variable for variable in variables if variable.name]
        equations = [str(item).strip() for item in data.get("equations") or [] if str(item).strip()]
        return cls(
            problem_type=problem_type or "unsupported",
            variables=variables,
            equations=equations,
            unknowns=_text_list(data.get("unknowns")),
            visualization_hint=str(data.get("visualization_hint", "")).strip(),
            parameters_for_sliders=_text_list(data.get("parameters_for_sliders")),
            assumptions=_text_list(data.get("assumptions")),
            source_text=str(data.get("source_text", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_type": self.problem_type,
            "variables": [variable.to_dict() for variable in self.variables],
            "equations": list(self.equations),
            "unknowns": list(self.unknowns),
            "visualization_hint": self.visualization_hint,
            "parameters_for_sliders": list(self.parameters_for_sliders),
            "assumptions": list(self.assumptions),
            "source_text": self.source_text,
        }

    @property
    def supported(self) -> bool:
        """``True`` when one of the four templates can draw it."""
        return self.problem_type in SUPPORTED_TYPES

    def value(self, name: str, default: float = 0.0) -> float:
        """The value of a variable (0 when it is not in the model)."""
        for variable in self.variables:
            if variable.name == name:
                return float(variable.value) if variable.value is not None else default
        return default

    def number(self, name: str) -> float:
        """The value of a variable - an error when it is missing."""
        for variable in self.variables:
            if variable.name == name:
                if variable.value is None:
                    raise SolveError(f"The value of {name!r} is missing")
                return float(variable.value)
        raise SolveError(f"The variable {name!r} is missing from the model")

    def unit(self, name: str) -> str:
        """The unit of a variable."""
        for variable in self.variables:
            if variable.name == name:
                return variable.unit
        return ""

    def symbols(self) -> dict[str, sympy.Expr]:
        """The variable table for SymPy (the values plus the assumptions)."""
        table: dict[str, sympy.Expr] = {}
        for variable in self.variables:
            if variable.value is None:
                continue
            table[variable.name] = sympy.Float(variable.value)
        for assumption in self.assumptions:
            match = _ASSUMPTION_RE.match(assumption)
            if match:
                table.setdefault(match.group(1), sympy.Float(match.group(2)))
        return table

    def slider_specs(self) -> list[ParamSpec]:
        """The sliders that the template offers."""
        specs: list[ParamSpec] = []
        names = self.parameters_for_sliders or [
            variable.name for variable in self.variables if variable.value is not None
        ]
        for name in names:
            value = self.value(name, 1.0)
            specs.append(
                ParamSpec(
                    name=name,
                    default=value,
                    min=max(value * 0.1, 0.1) if value else 0.1,
                    max=value * 3.0 if value else 10.0,
                    step=0.1,
                )
            )
        return specs

    def confirmation_card(self) -> dict[str, Any]:
        """The "here is how I understood the problem" card."""
        return {
            "problem_type": self.problem_type,
            "supported": self.supported,
            "variables": [variable.to_dict() for variable in self.variables],
            "equations": list(self.equations),
            "unknowns": list(self.unknowns),
            "assumptions": list(self.assumptions),
            "visualization_hint": self.visualization_hint,
        }


@dataclass
class WordProblemSolution:
    """The answer of a word problem."""

    values: dict[str, float] = field(default_factory=dict)
    latex: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "values": dict(self.values),
            "latex": dict(self.latex),
            "warnings": list(self.warnings),
            "steps": [step.to_dict() for step in self.steps],
        }

    @property
    def answer_text(self) -> str:
        """A readable summary of the answer."""
        return ", ".join(f"{name} = {value:.4g}" for name, value in self.values.items())


def solve_word_problem(problem: WordProblem) -> WordProblemSolution:
    """Solve the word problem with the template of its type."""
    if not problem.supported:
        raise SolveError(
            f"The problem type {problem.problem_type!r} is not supported. "
            f"Supported: {', '.join(SUPPORTED_TYPES)}."
        )
    from aieva.plugins.math.templates import get_template

    template = get_template(problem.problem_type)
    solution = template.solve(problem)
    solution.warnings.extend(_sanity_checks(problem, solution))
    return solution


def visualize_word_problem(
    problem: WordProblem, solution: WordProblemSolution
) -> VisualizationResult:
    """Draw the word problem with the template of its type."""
    if not problem.supported:
        raise SolveError(f"Nothing to draw for {problem.problem_type!r}")
    from aieva.plugins.math.templates import get_template

    template = get_template(problem.problem_type)
    result = template.render(problem, solution)
    if not result.parameters:
        result.parameters = problem.slider_specs()
    return result


def _sanity_checks(problem: WordProblem, solution: WordProblemSolution) -> list[str]:
    """The sanity checks of the plan (time, units, positive numbers)."""
    warnings: list[str] = []
    for name, value in solution.values.items():
        if "time" in name.lower() and value < 0:
            warnings.append(f"{name} is negative - check the data.")
    for variable in problem.variables:
        if variable.value is not None and variable.value < 0:
            warnings.append(f"{variable.name} is negative ({variable.value:g}).")
        if variable.value is not None and not variable.unit:
            warnings.append(f"{variable.name} has no unit - is that intended?")
    if not solution.values:
        warnings.append("The problem was solved but no value was found.")
    return warnings


class WordProblemSession:
    """A live word problem.

    The sliders change one value of the model; the problem is solved and drawn
    again. The object implements the
    :class:`~aieva.core.models.VisualizationSession` protocol, so the UI can
    drive it exactly like the equation plots.
    """

    def __init__(self, problem: WordProblem) -> None:
        self.problem = problem
        self.solution = solve_word_problem(problem)
        self.result = visualize_word_problem(problem, self.solution)
        self._params: dict[str, float] = {
            spec.name: spec.default for spec in self.result.parameters
        }

    # ------------------------------------------------------------------ api
    @property
    def figure(self) -> Any:
        """The figure that is shown."""
        return self.result.figure

    @property
    def parameters(self) -> list[ParamSpec]:
        """The sliders the UI has to offer."""
        return self.result.parameters

    @property
    def params(self) -> dict[str, float]:
        """The current value of every parameter."""
        return dict(self._params)

    @property
    def info(self) -> Any:
        """A short description of the answer (the plot modal shows it)."""
        return self.solution

    def set_param(self, name: str, value: float) -> float:
        """Set one value of the model and draw it again (milliseconds)."""
        import time

        start = time.perf_counter()
        for variable in self.problem.variables:
            if variable.name == name:
                variable.value = float(value)
        self._params[name] = float(value)
        try:
            self.solution = solve_word_problem(self.problem)
            self.result = visualize_word_problem(self.problem, self.solution)
        except SolveError:
            # the value does not work - keep the last good picture
            pass
        return (time.perf_counter() - start) * 1000.0

    def set_params(self, values: Any) -> float:
        """Set several values at once."""
        elapsed = 0.0
        items = values.items() if hasattr(values, "items") else values
        for name, value in items:
            elapsed += self.set_param(str(name), float(value))
        return elapsed

    def reset_params(self) -> float:
        """Put every value back to the value of the model."""
        elapsed = 0.0
        for spec in self.result.parameters:
            elapsed += self.set_param(spec.name, spec.default)
        return elapsed

    def animation_points(self) -> dict[str, Any] | None:
        """The points of the animation (only the projectile has one)."""
        if self.problem.problem_type != "kinematic_projectile":
            return None
        from aieva.plugins.math.templates import kinematic

        return kinematic.animation_points(self.problem, self.solution)


# --------------------------------------------------------------------- offline
#: The keywords that decide the template when there is no LLM.
_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "rate_tank": (
        "tank",
        "fill",
        "filled",
        "empties",
        "drain",
        "tap",
        "l/min",
        "litres",
        "liters",
        "flow",
    ),
    "geometry": ("rectangle", "circle", "triangle", "perimeter", "circumference", "radius"),
    "optimization": (
        "largest",
        "smallest",
        "maximum",
        "minimize",
        "maximize",
        "optimum",
        "best",
        "fence",
    ),
    "uniform_motion": (
        "catch",
        "meet",
        "chase",
        "towards",
        "toward",
        "train",
        "bus",
        "cyclist",
        "car",
    ),
    "kinematic_projectile": (
        "throw",
        "thrown",
        "kicked",
        "projectile",
        "ball",
        "angle",
        "trajectory",
        "flight",
    ),
}

#: ``30 m/s`` and friends.
_SPEED_RE = re.compile(r"(-?[0-9]+(?:\.[0-9]+)?)\s*(?:m/s|mps|km/h)", re.IGNORECASE)
#: ``45 degrees`` and friends.
_ANGLE_RE = re.compile(r"(-?[0-9]+(?:\.[0-9]+)?)\s*(?:deg\b|degree|°)", re.IGNORECASE)
#: ``30 l/min`` - the flow.
_FLOW_RE = re.compile(r"(-?[0-9]+(?:\.[0-9]+)?)\s*(?:l/min|liter/min|litre/min)", re.IGNORECASE)
#: ``600 l`` / ``600 litres`` (but not ``600 l/min``).
_VOLUME_RE = re.compile(r"(-?[0-9]+(?:\.[0-9]+)?)\s*(?:litres|liters|l\b)(?!\s*/)", re.IGNORECASE)
#: ``40 m`` (but not ``40 m/s``).
_LENGTH_RE = re.compile(r"(-?[0-9]+(?:\.[0-9]+)?)\s*(?:metres|meters|m\b)(?!\s*/)", re.IGNORECASE)


def _numbers(pattern: re.Pattern[str], text: str) -> list[float]:
    return [float(match.group(1)) for match in pattern.finditer(text)]


def guess_problem_type(text: str) -> str:
    """The template that fits the text best (the fallback without the LLM)."""
    lowered = (text or "").lower()
    best_type = "unsupported"
    best_score = 0
    for problem_type, keywords in _TYPE_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in lowered)
        if score > best_score:
            best_type = problem_type
            best_score = score
    return best_type


def local_model(text: str) -> WordProblem:
    """A model without the LLM.

    The keywords pick the template and the numbers in the text become the
    variables. It is not as good as the LLM, but it keeps the application
    usable when the server (or the key) is missing.
    """
    text = (text or "").strip()
    problem_type = guess_problem_type(text)
    speeds = _numbers(_SPEED_RE, text)
    angles = _numbers(_ANGLE_RE, text)
    flows = _numbers(_FLOW_RE, text)
    volumes = _numbers(_VOLUME_RE, text)
    lengths = _numbers(_LENGTH_RE, text)

    if problem_type == "kinematic_projectile":
        variables = [
            ProblemVariable("v0", "initial speed", speeds[0] if speeds else 20.0, "m/s"),
            ProblemVariable("theta", "launch angle", angles[0] if angles else 45.0, "deg"),
            ProblemVariable("g", "gravity", 9.8, "m/s^2"),
        ]
        equations = ["y = v0*sin(theta)*t - 0.5*g*t**2", "x = v0*cos(theta)*t"]
        sliders = ["v0", "theta"]
    elif problem_type == "uniform_motion":
        first = speeds[0] if speeds else 10.0
        second = speeds[1] if len(speeds) > 1 else 5.0
        start_two = lengths[0] if lengths else 100.0
        variables = [
            ProblemVariable("v1", "speed of the first object", first, "m/s"),
            ProblemVariable("v2", "speed of the second object", second, "m/s"),
            ProblemVariable("x1", "start of the first object", 0.0, "m"),
            ProblemVariable("x2", "start of the second object", start_two, "m"),
        ]
        equations = ["x1 = 0 + v1*t", f"x2 = {start_two:g} + v2*t"]
        sliders = ["v1", "v2"]
    elif problem_type == "optimization":
        limit = lengths[0] if lengths else 40.0
        variables = [
            ProblemVariable("L", "the length that is available", limit, "m"),
            ProblemVariable("x_min", "smallest side", 0.0, "m"),
            ProblemVariable("x_max", "largest side", limit, "m"),
        ]
        equations = ["A = x*(L - x)"]
        sliders = ["x_min", "x_max"]
    elif problem_type == "rate_tank":
        variables = [
            ProblemVariable("inflow", "what comes in", flows[0] if flows else 20.0, "L/min"),
            ProblemVariable(
                "outflow", "what goes out", flows[1] if len(flows) > 1 else 0.0, "L/min"
            ),
            ProblemVariable(
                "volume", "capacity of the tank", volumes[0] if volumes else 100.0, "L"
            ),
            ProblemVariable("initial", "water in the tank", 0.0, "L"),
        ]
        equations = ["V = V0 + (inflow - outflow)*t"]
        sliders = ["inflow", "outflow"]
    elif problem_type == "geometry":
        first = lengths[0] if lengths else 5.0
        second = lengths[1] if len(lengths) > 1 else 8.0
        if "circle" in text.lower() or "radius" in text.lower():
            variables = [ProblemVariable("r", "radius", first, "m")]
            equations = ["A = pi*r**2"]
        elif "triangle" in text.lower():
            variables = [
                ProblemVariable("a", "first side", first, "m"),
                ProblemVariable("b", "second side", second, "m"),
            ]
            equations = ["A = a*b/2", "c = sqrt(a**2 + b**2)"]
        else:
            variables = [
                ProblemVariable("w", "width", first, "m"),
                ProblemVariable("h", "height", second, "m"),
            ]
            equations = ["A = w*h"]
        sliders = []
    else:
        variables = []
        equations = []
        sliders = []

    return WordProblem(
        problem_type=problem_type,
        variables=variables,
        equations=equations,
        unknowns=[],
        visualization_hint="",
        parameters_for_sliders=sliders,
        assumptions=[],
        source_text=text,
    )


__all__ = [
    "KNOWN_BUT_UNSUPPORTED",
    "SUPPORTED_TYPES",
    "ProblemVariable",
    "WordProblem",
    "WordProblemSession",
    "WordProblemSolution",
    "guess_problem_type",
    "local_model",
    "solve_word_problem",
    "visualize_word_problem",
]
