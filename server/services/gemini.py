"""The Gemini service of the Aieva server.

The service is the only place that talks to Google. It

* sends strict JSON prompts (``response_mime_type="application/json"``),
* retries twice with an exponential backoff,
* falls back to the mock answers when ``AIEVA_MOCK_LLM=true`` or when no API
  key is configured, so the app and the tests work without a key.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from aieva.config import get_settings
from aieva.core.errors import CloudError
from aieva.core.llm.prompts import REPAIR_PROMPT

LOGGER = logging.getLogger(__name__)

#: The number of retries after the first attempt.
MAX_RETRIES = 2

#: The base of the exponential backoff (seconds).
BACKOFF_BASE = 0.5

#: The canned answers of the mock mode.
MOCK_OCR = {
    "latex": "y = x^2 + 3x",
    "plain": "y = x**2 + 3*x",
    "confidence_note": "mock answer - the LLM was not called",
    "kind": "equation",
}

MOCK_EXPLAIN = {
    "steps": [
        {
            "title": "Move everything to one side",
            "explanation": "Subtract the right hand side so that the equation becomes zero.",
            "latex": "x^2 + 3x - 2 = 0",
        },
        {
            "title": "Use the quadratic formula",
            "explanation": "The discriminant decides how many real roots there are.",
            "latex": "x = \\frac{-3 \\pm \\sqrt{17}}{2}",
        },
    ],
    "note": "mock answer - the LLM was not called",
}

MOCK_WORDPROBLEM = {
    "problem_type": "kinematic_projectile",
    "variables": [
        {
            "name": "v0",
            "description": "initial speed",
            "value": 20,
            "unit": "m/s",
        },
        {
            "name": "theta",
            "description": "launch angle",
            "value": 45,
            "unit": "deg",
        },
    ],
    "equations": ["y = v0*sin(theta)*t - 0.5*g*t**2"],
    "unknowns": ["max_height"],
    "visualization_hint": "trajectory with velocity vectors",
    "parameters_for_sliders": ["v0", "theta"],
    "assumptions": ["g = 9.8 m/s^2"],
}


def extract_json(text: str) -> Any:
    """Pull the JSON out of an answer that may contain a markdown fence."""
    if not text:
        raise CloudError("The model did not answer")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as exc:
                raise CloudError(f"The model did not answer with valid JSON: {exc}") from exc
        raise CloudError("The model did not answer with valid JSON") from None


class GeminiService:
    """Talks to Gemini (or to the mock answers)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        mock: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.mock = settings.mock_llm if mock is None else mock
        self._client: Any = None

    # ------------------------------------------------------------------ api
    @property
    def available(self) -> bool:
        """``True`` when a real call is possible."""
        return bool(self.api_key) and not self.mock

    def complete_json(
        self,
        prompt: str,
        image_bytes: bytes | None = None,
        mime_type: str = "image/png",
    ) -> Any:
        """Send a prompt and return the parsed JSON answer."""
        if not self.available:
            raise CloudError("No Gemini API key is configured")
        answer = self._call_with_retries(prompt, image_bytes, mime_type)
        try:
            return extract_json(answer)
        except CloudError:
            # one repair attempt with the broken answer
            LOGGER.warning("The model did not answer with JSON - asking for a repair")
            repaired = self._call_with_retries(REPAIR_PROMPT.format(broken=answer), None, mime_type)
            return extract_json(repaired)

    # ------------------------------------------------------------ internals
    def _client_or_create(self) -> Any:
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - the SDK is optional
                raise CloudError("The google-genai package is not installed") from exc
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _call_with_retries(self, prompt: str, image_bytes: bytes | None, mime_type: str) -> str:
        """One request with two retries and an exponential backoff."""
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return self._call_once(prompt, image_bytes, mime_type)
            except Exception as exc:  # noqa: BLE001 - the SDK raises many types
                last_error = exc
                if attempt >= MAX_RETRIES:
                    break
                delay = BACKOFF_BASE * (2**attempt)
                LOGGER.warning(
                    "Gemini call failed (%s) - retry %d in %.1fs", exc, attempt + 1, delay
                )
                time.sleep(delay)
        raise CloudError(f"Gemini could not be reached: {last_error}")

    def _call_once(self, prompt: str, image_bytes: bytes | None, mime_type: str) -> str:
        from google.genai import types

        client = self._client_or_create()
        parts: list[Any] = [types.Part.from_text(text=prompt)]
        if image_bytes:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        response = client.models.generate_content(
            model=self.model,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            raise CloudError("The model did not answer")
        return str(text)


__all__ = [
    "BACKOFF_BASE",
    "MAX_RETRIES",
    "MOCK_EXPLAIN",
    "MOCK_OCR",
    "MOCK_WORDPROBLEM",
    "GeminiService",
    "extract_json",
]
