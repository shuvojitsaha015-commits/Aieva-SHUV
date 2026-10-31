"""``POST /api/math/wordproblem`` - a word problem becomes a structured model.

The model follows the schema of Phase 9 (four supported template categories).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from aieva.core.errors import AievaError
from aieva.core.llm.prompts import WORDPROBLEM_PROMPT
from server.schemas import (
    ProblemVariable,
    WordProblemRequest,
    WordProblemResponse,
)
from server.services.gemini import MOCK_WORDPROBLEM, GeminiService

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/api/math", tags=["math"])

#: The problem types that v1 supports.
SUPPORTED_TYPES = (
    "kinematic_projectile",
    "uniform_motion",
    "optimization",
    "rate_tank",
    "geometry",
)


@router.post("/wordproblem", response_model=WordProblemResponse)
async def wordproblem(request: WordProblemRequest) -> WordProblemResponse:
    """Turn a word problem into the structured model of Phase 9."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="The problem text is empty")

    service = GeminiService()
    if not service.available:
        LOGGER.info("The mock word problem answered (no key configured)")
        return WordProblemResponse(**MOCK_WORDPROBLEM)

    prompt = WORDPROBLEM_PROMPT.format(text=request.text)
    from starlette.concurrency import run_in_threadpool

    try:
        answer = await run_in_threadpool(service.complete_json, prompt)
    except AievaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("The word problem call failed")
        raise HTTPException(status_code=502, detail=f"The call failed: {exc}") from exc

    if not isinstance(answer, dict):
        raise HTTPException(status_code=502, detail="The model did not answer with an object")

    variables = []
    for raw in answer.get("variables") or []:
        if not isinstance(raw, dict):
            continue
        value = raw.get("value")
        variables.append(
            ProblemVariable(
                name=str(raw.get("name", "")),
                description=str(raw.get("description", "")),
                value=float(value) if isinstance(value, (int, float)) else None,
                unit=str(raw.get("unit", "")),
            )
        )
    return WordProblemResponse(
        problem_type=str(answer.get("problem_type", "unsupported")),
        variables=variables,
        equations=[str(item) for item in answer.get("equations") or []],
        unknowns=[str(item) for item in answer.get("unknowns") or []],
        visualization_hint=str(answer.get("visualization_hint", "")),
        parameters_for_sliders=[str(item) for item in answer.get("parameters_for_sliders") or []],
        assumptions=[str(item) for item in answer.get("assumptions") or []],
        note=(
            ""
            if answer.get("problem_type") in SUPPORTED_TYPES
            else "This problem type is not supported in v1."
        ),
        raw=answer,
    )


__all__ = ["SUPPORTED_TYPES", "router"]
