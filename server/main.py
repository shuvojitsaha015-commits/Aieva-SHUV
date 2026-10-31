"""The Aieva fog server.

Run it with::

    uvicorn server.main:app --host 0.0.0.0 --port 8000

or use ``scripts/run_server.sh``.

The server is the part of Aieva that may talk to the cloud: it reads the
mathematics of a picture (Gemini Vision), explains a solution and turns a word
problem into a structured model. Everything else runs on the device.

Protection against random use:

* the ``X-Aieva-Key`` header (when a key is configured),
* a simple per IP rate limit,
* the size limits (5 MB per image, 4000 characters per text).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from aieva.config import get_settings
from server.routers import explain, health, ocr, wordproblem

LOGGER = logging.getLogger(__name__)

#: The version of the API.
API_VERSION = "1.0.0"

#: The requests per minute and per IP.
RATE_LIMIT_PER_MINUTE = 30

#: The header that carries the shared key.
API_KEY_HEADER = "X-Aieva-Key"


class RateLimiter:
    """A small in-memory rate limiter (per IP)."""

    def __init__(self, limit: int = RATE_LIMIT_PER_MINUTE, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """``True`` when the request may pass."""
        now = time.time()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        """Forget every hit (used by the tests)."""
        self._hits.clear()


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title="Aieva Math Server",
        version=API_VERSION,
        description="The fog server of Aieva: OCR, explanations and word problems.",
    )
    limiter = RateLimiter()
    application.state.limiter = limiter

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def guard(request: Request, call_next: Any) -> Any:
        """The API key and the rate limit."""
        if request.url.path.startswith("/api/"):
            key = settings.server_api_key
            if key and request.headers.get(API_KEY_HEADER, "") != key:
                return JSONResponse(
                    status_code=401, content={"detail": "A valid X-Aieva-Key is required"}
                )
            client = request.client.host if request.client else "unknown"
            if not request.app.state.limiter.allow(client):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests - please wait a moment"},
                )
        return await call_next(request)

    @application.exception_handler(Exception)
    async def on_error(_request: Request, exc: Exception) -> JSONResponse:
        """Every error becomes a clean JSON answer."""
        LOGGER.exception("The request failed")
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    application.include_router(health.router)
    application.include_router(ocr.router)
    application.include_router(explain.router)
    application.include_router(wordproblem.router)
    return application


app = create_app()


__all__ = [
    "API_KEY_HEADER",
    "API_VERSION",
    "RATE_LIMIT_PER_MINUTE",
    "RateLimiter",
    "app",
    "create_app",
]
