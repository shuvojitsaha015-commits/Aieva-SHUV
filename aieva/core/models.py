"""Core data models shared by the core, the plugins and the UI.

These are plain dataclasses on purpose: they must stay importable without Kivy
and be trivially serialisable for the cache and the JSON history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

InputKind = Literal["text", "latex", "image", "document"]
"""Where the input came from / how it should be interpreted."""


@dataclass
class Step:
    """One step of a step-by-step solution."""

    title: str
    explanation: str
    latex: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "explanation": self.explanation, "latex": self.latex}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Step:
        return cls(
            title=str(data.get("title", "")),
            explanation=str(data.get("explanation", "")),
            latex=data.get("latex"),
        )


@dataclass
class ParsedInput:
    """The normalised representation of whatever the user handed us."""

    raw: str
    kind: InputKind = "text"
    latex: str | None = None
    sympy_expr: Any | None = None
    source: str = "manual"
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "kind": self.kind,
            "latex": self.latex,
            "sympy_expr": repr(self.sympy_expr) if self.sympy_expr is not None else None,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class ParamSpec:
    """Description of one slider parameter."""

    name: str
    default: float = 1.0
    min: float = -10.0
    max: float = 10.0
    step: float = 0.1

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "default": self.default,
            "min": self.min,
            "max": self.max,
            "step": self.step,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParamSpec:
        return cls(
            name=str(data["name"]),
            default=float(data.get("default", 1.0)),
            min=float(data.get("min", -10.0)),
            max=float(data.get("max", 10.0)),
            step=float(data.get("step", 0.1)),
        )


@dataclass
class SolveResult:
    """The outcome of solving a problem."""

    problem_type: str
    answer_latex: str = ""
    answer_text: str = ""
    steps: list[Step] = field(default_factory=list)
    verified: bool | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_type": self.problem_type,
            "answer_latex": self.answer_latex,
            "answer_text": self.answer_text,
            "steps": [s.to_dict() for s in self.steps],
            "verified": self.verified,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SolveResult:
        return cls(
            problem_type=str(data.get("problem_type", "unknown")),
            answer_latex=str(data.get("answer_latex", "")),
            answer_text=str(data.get("answer_text", "")),
            steps=[Step.from_dict(s) for s in data.get("steps", [])],
            verified=data.get("verified"),
            warnings=list(data.get("warnings", [])),
        )


@dataclass
class VisualizationResult:
    """A figure (or image) plus the parameters the UI should offer sliders for."""

    figure: Any | None = None
    image_bytes: bytes | None = None
    parameters: list[ParamSpec] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_figure": self.figure is not None,
            "has_image": self.image_bytes is not None,
            "parameters": [p.to_dict() for p in self.parameters],
            "meta": dict(self.meta),
        }


@runtime_checkable
class VisualizationSession(Protocol):
    """An interactive visualisation the UI can drive with sliders.

    Every subject plugin that supports dynamic parameters returns an object
    implementing this protocol from
    :meth:`~aieva.core.plugin_base.SubjectPlugin.create_session`. The UI only
    knows this protocol - never a specific maths class.
    """

    #: The Matplotlib figure that is displayed.
    figure: Any
    #: The parameters the UI must offer a slider for.
    parameters: list[ParamSpec]

    def set_param(self, name: str, value: float) -> float:
        """Set one parameter and redraw. Returns the duration in milliseconds."""
        ...

    def set_params(self, values: Any) -> float:
        """Set several parameters at once and redraw."""
        ...

    def reset_params(self) -> float:
        """Reset every parameter to its default and redraw."""
        ...


__all__ = [
    "InputKind",
    "ParamSpec",
    "ParsedInput",
    "SolveResult",
    "Step",
    "VisualizationResult",
    "VisualizationSession",
]
