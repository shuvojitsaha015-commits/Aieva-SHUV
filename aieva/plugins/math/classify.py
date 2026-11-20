"""The problem classifier (feature 1.e).

The rules work without the network: the shape of the input decides the type.
The LLM is only used as a fallback for the inputs that the rules do not
understand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: Every problem type that the solver understands.
PROBLEM_TYPES: tuple[str, ...] = (
    "equation_solve",
    "inequality",
    "system",
    "derivative",
    "integral",
    "definite_integral",
    "limit",
    "simplify",
    "expand_factor",
    "matrix_op",
    "plot_only",
    "word_problem",
)

#: The words that mark a word problem.
_WORD_HINTS = (
    "how many",
    "how much",
    "how fast",
    "how long",
    "a ball",
    "a tank",
    "a car",
    "a tank",
    "per hour",
    "per minute",
    "per second",
    "value of",
    "find the",
    "a farmer",
    "a rope",
    "a rectangle",
    "maximum",
    "minimum",
)

_MATRIX_RE = re.compile(r"\[\[.*\]\]")
_INTEGRAL_RE = re.compile(r"\\int\b|\\int_|\bintegrate\b|\bintegral\b", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\\lim\b|\\lim_|\blimit\b|\blim\b", re.IGNORECASE)
_DERIVATIVE_RE = re.compile(
    r"\\frac\s*\{d\}\s*\{d\w\}|\bd/d\w\b|\bdifferentiate\b|\bderivative\b|\bdiff\b", re.IGNORECASE
)
_INEQUALITY_RE = re.compile(r"(?<!-)(>=|<=|>|<|\\geq|\\leq|\\gt|\\lt)")
_EQUATION_RE = re.compile(r"=")


@dataclass
class Classification:
    """The result of the classifier."""

    problem_type: str
    confidence: float = 1.0
    reason: str = ""
    source: str = "rules"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_type": self.problem_type,
            "confidence": self.confidence,
            "reason": self.reason,
            "source": self.source,
            "raw": dict(self.raw),
        }


def classify(text: str) -> Classification:
    """Work out what kind of problem ``text`` is."""
    raw = (text or "").strip()
    if not raw:
        return Classification("plot_only", 0.0, "nothing to classify")

    lowered = raw.lower()

    if _MATRIX_RE.search(raw):
        return Classification("matrix_op", 0.9, "the input contains a matrix")

    if _INTEGRAL_RE.search(raw):
        definite = bool(
            re.search(
                r"\\int\s*[_^]|\\int_[^{]*\^|\\int\s*\\d|\bintegral\s*\([^,]+,\s*\([^,]+,\s*[^,]+,\s*[^,\)]+\)",
                raw,
                re.IGNORECASE,
            )
        )
        if definite or re.search(r"\d\s*(to|,)\s*\d", lowered):
            return Classification(
                "definite_integral", 0.9, "the input contains a definite integral"
            )
        return Classification("integral", 0.9, "the input contains an integral")

    if _LIMIT_RE.search(raw):
        return Classification("limit", 0.9, "the input contains a limit")

    if _DERIVATIVE_RE.search(raw):
        return Classification("derivative", 0.9, "the input contains a derivative")

    if re.search(r"\bsimplif", lowered):
        return Classification("simplify", 0.9, "the input asks to simplify")

    if re.search(r"\b(factor|expand)\b", lowered):
        return Classification("expand_factor", 0.9, "the input asks to factor or expand")

    equations = [part for part in re.split(r"[;\n]", raw) if part.strip()]
    if len(equations) > 1 and all("=" in part for part in equations):
        return Classification("system", 0.85, "the input contains several equations")

    if _INEQUALITY_RE.search(raw):
        return Classification("inequality", 0.85, "the input contains an inequality")

    if _EQUATION_RE.search(raw):
        # y = f(x) is a function to plot, not an equation to solve
        left, _, right = raw.partition("=")
        if re.fullmatch(r"\s*[A-Za-z_][A-Za-z_0-9]*\s*", left) and left.strip() not in right:
            return Classification("plot_only", 0.8, "the input defines a function")
        return Classification("equation_solve", 0.8, "the input is an equation")

    if any(hint in lowered for hint in _WORD_HINTS):
        return Classification("word_problem", 0.7, "the input reads like a word problem")

    if re.search(r"[a-zA-Z]\s*[\^]|\*\*|\bsin\b|\bcos\b|\btan\b|\bexp\b|\blog\b", raw):
        return Classification("plot_only", 0.6, "the input looks like a function to plot")

    return Classification("plot_only", 0.4, "nothing matched - plotting is the safe choice")


def classify_with_llm(text: str, fallback: Classification | None = None) -> Classification:
    """Ask the server when the rules are not sure (falls back to the rules).

    The server is optional: when it cannot be reached, the rule based answer
    is used.
    """
    from aieva.core.errors import CloudError
    from aieva.core.llm.client import AievaServerClient

    rules = fallback or classify(text)
    if rules.confidence >= 0.6:
        return rules
    try:
        answer = AievaServerClient().word_problem(text)
    except CloudError:
        return rules
    problem_type = str(answer.get("problem_type", "")) if isinstance(answer, dict) else ""
    if problem_type == "unsupported":
        return rules
    return Classification(
        problem_type="word_problem",
        confidence=0.5,
        reason="the server recognised a word problem",
        source="llm",
        raw=answer,
    )


__all__ = ["PROBLEM_TYPES", "Classification", "classify", "classify_with_llm"]
