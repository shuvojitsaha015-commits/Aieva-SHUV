"""The request and response models of the Aieva server.

The models are the contract of the API - every answer is checked against
them before it leaves the server.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

#: The biggest image the server accepts (5 MB).
MAX_IMAGE_BYTES = 5 * 1024 * 1024

#: The biggest text the server accepts.
MAX_TEXT_CHARS = 4000


class HealthResponse(BaseModel):
    """The answer of ``GET /health``."""

    status: str = "ok"
    mock: bool = False
    model: str = ""
    version: str = "1.0.0"


class OcrResponse(BaseModel):
    """The answer of ``POST /api/math/ocr``."""

    latex: str = ""
    plain: str = ""
    confidence_note: str = ""
    kind: str = "unknown"
    #: What should be done with the problem (``solve``, ``graph``, ``both``,
    #: ``none``) - the model decides, the rules are only the fallback.
    intent: str = ""
    #: The table of values the model read (``None`` when there is no table).
    chart: dict[str, object] | None = None


class ExplainRequest(BaseModel):
    """The body of ``POST /api/math/explain``."""

    problem_latex: str = Field(default="", max_length=MAX_TEXT_CHARS)
    sympy_answer: str = Field(default="", max_length=MAX_TEXT_CHARS)
    hints: str = Field(default="", max_length=MAX_TEXT_CHARS)


class Step(BaseModel):
    """One step of a solution."""

    title: str = ""
    explanation: str = ""
    latex: str = ""


class ExplainResponse(BaseModel):
    """The answer of ``POST /api/math/explain``."""

    steps: list[Step] = Field(default_factory=list)
    note: str = ""


class WordProblemRequest(BaseModel):
    """The body of ``POST /api/math/wordproblem``."""

    text: str = Field(default="", max_length=MAX_TEXT_CHARS)


class ProblemVariable(BaseModel):
    """One variable of a word problem."""

    name: str = ""
    description: str = ""
    value: float | None = None
    unit: str = ""


class WordProblemResponse(BaseModel):
    """The answer of ``POST /api/math/wordproblem``."""

    problem_type: str = "unsupported"
    variables: list[ProblemVariable] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    visualization_hint: str = ""
    parameters_for_sliders: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    note: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """The body of every error answer."""

    detail: str = ""
    code: str = "error"


__all__ = [
    "MAX_IMAGE_BYTES",
    "MAX_TEXT_CHARS",
    "ErrorResponse",
    "ExplainRequest",
    "ExplainResponse",
    "HealthResponse",
    "OcrResponse",
    "ProblemVariable",
    "Step",
    "WordProblemRequest",
    "WordProblemResponse",
]
