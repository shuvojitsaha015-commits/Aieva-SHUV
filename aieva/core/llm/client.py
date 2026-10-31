"""The client that talks to the Aieva server.

The desktop app never talks to Google directly - it asks the fog server, which
keeps the API key on the server and lets the app work on a board without an
internet connection (in that case the server answers with the mock data or
the app falls back to the manual input).
"""

from __future__ import annotations

import logging
from typing import Any

from aieva.config import get_settings
from aieva.core.errors import CloudError

LOGGER = logging.getLogger(__name__)


class AievaServerClient:
    """A tiny HTTP client for the Aieva server."""

    def __init__(
        self,
        server_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        self.server_url = (server_url or settings.server_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.server_api_key
        self.timeout = timeout if timeout is not None else settings.server_timeout

    # ------------------------------------------------------------------ api
    def health(self) -> dict[str, Any]:
        """``GET /health``."""
        return self._get("/health")

    def explain(
        self, problem_latex: str, sympy_answer: str, hints: str = ""
    ) -> list[dict[str, str]]:
        """``POST /api/math/explain`` - the steps of a verified solution."""
        payload = self._post(
            "/api/math/explain",
            {
                "problem_latex": problem_latex,
                "sympy_answer": sympy_answer,
                "hints": hints,
            },
        )
        steps = payload.get("steps") if isinstance(payload, dict) else None
        return steps if isinstance(steps, list) else []

    def word_problem(self, text: str) -> dict[str, Any]:
        """``POST /api/math/wordproblem`` - the structured model of Phase 9."""
        payload = self._post("/api/math/wordproblem", {"text": text})
        return payload if isinstance(payload, dict) else {}

    def ocr(
        self, image_bytes: bytes, filename: str = "capture.png", mime_type: str = "image/png"
    ) -> dict[str, Any]:
        """``POST /api/math/ocr`` - read the mathematics of a picture."""
        return self._post_file("/api/math/ocr", image_bytes, filename, mime_type)

    # ------------------------------------------------------------ internals
    def _headers(self) -> dict[str, str]:
        return {"X-Aieva-Key": self.api_key} if self.api_key else {}

    def _get(self, path: str) -> dict[str, Any]:
        import httpx

        try:
            response = httpx.get(
                f"{self.server_url}{path}", headers=self._headers(), timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise CloudError(f"The Aieva server could not be reached: {exc}") from exc

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        import httpx

        try:
            response = httpx.post(
                f"{self.server_url}{path}",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise CloudError(f"The Aieva server could not be reached: {exc}") from exc

    def _post_file(self, path: str, data: bytes, filename: str, mime_type: str) -> Any:
        import httpx

        try:
            response = httpx.post(
                f"{self.server_url}{path}",
                files={"image": (filename, data, mime_type)},
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise CloudError(f"The Aieva server could not be reached: {exc}") from exc


__all__ = ["AievaServerClient"]
