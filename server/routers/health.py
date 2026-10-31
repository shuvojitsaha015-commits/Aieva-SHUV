"""``GET /health`` - is the server alive?"""

from __future__ import annotations

from fastapi import APIRouter

from aieva.config import get_settings
from server.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """The health of the server (used by the app before it starts)."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        mock=settings.mock_llm or not settings.has_gemini_key,
        model=settings.gemini_model,
    )


@router.get("/")
def index() -> dict[str, object]:
    """A short map of the server - the address that is opened by hand."""
    settings = get_settings()
    return {
        "service": "Aieva fog server",
        "version": "1.0.0",
        "mode": "mock" if (settings.mock_llm or not settings.has_gemini_key) else "live",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "ocr": "POST /api/math/ocr",
            "explain": "POST /api/math/explain",
            "wordproblem": "POST /api/math/wordproblem",
        },
    }


__all__ = ["router"]
