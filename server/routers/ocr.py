"""``POST /api/math/ocr`` - read the mathematics of a picture.

The route accepts a multipart image (at most 5 MB) and answers with strict
JSON: ``{"latex": ..., "plain": ..., "confidence_note": ..., "kind": ...}``.

The heavy work runs in a thread pool, so the event loop is never blocked.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from aieva.core.errors import AievaError
from aieva.core.llm.prompts import OCR_PROMPT
from server.schemas import MAX_IMAGE_BYTES, OcrResponse
from server.services.gemini import MOCK_OCR, GeminiService

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/api/math", tags=["math"])


@router.post("/ocr", response_model=OcrResponse)
async def ocr(image: UploadFile = File(...)) -> OcrResponse:
    """Read the mathematics out of the uploaded image."""
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The image is empty")
    if len(payload) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"The image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB",
        )

    service = GeminiService()
    if not service.available:
        LOGGER.info("The mock OCR answered (no key configured)")
        return OcrResponse(**MOCK_OCR)

    from starlette.concurrency import run_in_threadpool

    try:
        answer = await run_in_threadpool(
            service.complete_json, OCR_PROMPT, payload, image.content_type or "image/png"
        )
    except AievaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - the SDK raises many types
        LOGGER.exception("The OCR call failed")
        raise HTTPException(status_code=502, detail=f"The OCR call failed: {exc}") from exc

    if not isinstance(answer, dict):
        raise HTTPException(status_code=502, detail="The model did not answer with an object")
    return OcrResponse(
        latex=str(answer.get("latex", "")),
        plain=str(answer.get("plain", "")),
        confidence_note=str(answer.get("confidence_note", "")),
        kind=str(answer.get("kind", "unknown")),
    )


__all__ = ["router"]
