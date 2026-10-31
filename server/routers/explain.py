"""``POST /api/math/explain`` - explain a solution that SymPy verified.

The LLM only writes the explanation - the answer itself was computed with
SymPy on the device and must not change.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from aieva.core.errors import AievaError
from aieva.core.llm.prompts import EXPLAIN_PROMPT
from server.schemas import ExplainRequest, ExplainResponse, Step
from server.services.gemini import MOCK_EXPLAIN, GeminiService

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/api/math", tags=["math"])


@router.post("/explain", response_model=ExplainResponse)
async def explain(request: ExplainRequest) -> ExplainResponse:
    """Explain the verified answer step by step."""
    service = GeminiService()
    if not service.available:
        LOGGER.info("The mock explanation answered (no key configured)")
        return ExplainResponse(
            steps=[Step(**step) for step in MOCK_EXPLAIN["steps"]],
            note=MOCK_EXPLAIN["note"],
        )

    prompt = EXPLAIN_PROMPT.format(
        problem_latex=request.problem_latex or "(not given)",
        sympy_answer=request.sympy_answer or "(not given)",
        hints=request.hints or "(none)",
    )

    from starlette.concurrency import run_in_threadpool

    try:
        answer = await run_in_threadpool(service.complete_json, prompt)
    except AievaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("The explanation call failed")
        raise HTTPException(status_code=502, detail=f"The explanation call failed: {exc}") from exc

    raw_steps = answer.get("steps") if isinstance(answer, dict) else None
    if not isinstance(raw_steps, list):
        raise HTTPException(status_code=502, detail="The model did not answer with any steps")
    steps = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            continue
        steps.append(
            Step(
                title=str(raw.get("title", "")),
                explanation=str(raw.get("explanation", "")),
                latex=str(raw.get("latex", "")),
            )
        )
    return ExplainResponse(steps=steps, note=str(answer.get("note", "")))


__all__ = ["router"]
