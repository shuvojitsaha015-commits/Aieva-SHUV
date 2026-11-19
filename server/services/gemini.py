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
from collections.abc import Sequence
from typing import Any

from aieva.config import get_settings
from aieva.core.errors import CloudError
from aieva.core.llm.prompts import REPAIR_PROMPT, render_prompt

LOGGER = logging.getLogger(__name__)

#: The number of retries after the first attempt.
MAX_RETRIES = 2

#: The base of the exponential backoff (seconds).
BACKOFF_BASE = 0.5

#: The longest wait between two tries (seconds).
BACKOFF_MAX = 8.0

#: The words in an error that mean "try again later" - the server of
#: Google is busy, the network hiccuped, the quota of the minute is over.
TRANSIENT_MARKERS = (
    "503",
    "unavailable",
    "overloaded",
    "deadline exceeded",
    "timeout",
    "timed out",
    "429",
    "rate limit",
    "resource_exhausted",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
    "internal error",
    "502",
    "504",
)

#: The words in an error that mean "this key will not work" - no waiting
#: helps, the key is simply refused.
PERMANENT_MARKERS = (
    "400",
    "401",
    "403",
    "invalid_argument",
    "invalid api key",
    "api key not valid",
    "api_key_invalid",
    "permission_denied",
    "unauthenticated",
)

#: The canned answers of the mock mode.
MOCK_OCR = {
    "latex": "y = x^2 + 3x",
    "plain": "y = x**2 + 3*x",
    "confidence_note": "mock answer - the LLM was not called",
    "kind": "equation",
    "intent": "both",
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


def is_transient(exc: BaseException) -> bool:
    """``True`` when the same call could work a moment later.

    Google answers with "503 UNAVAILABLE" or a timeout when the service
    is busy - that is not a mistake of the program, so the call is simply
    tried again. A refused key ("400", "401") will never work, so it is
    not tried again.

    An error that says nothing at all (a network hiccup, an exception
    of the SDK) is **transient as well**: the old behaviour was to try
    again, and an unknown error must not make the answer worse.
    """
    text = str(exc).lower()
    return not any(marker in text for marker in PERMANENT_MARKERS)


def describe_failure(exc: BaseException) -> str:
    """A short, clear description of the failure for the teacher."""
    if not is_transient(exc):
        return f"Gemini refused the request - the API key has to be checked: {exc}"
    text = str(exc).lower()
    if any(marker in text for marker in TRANSIENT_MARKERS):
        return (
            "Gemini is temporarily unavailable (the service is busy or the "
            f"network hiccuped): {exc}"
        )
    return f"Gemini could not be reached: {exc}"


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
    """Talks to Gemini (or to the mock answers).

    **Several keys at the same time.** The service knows a *pool* of Gemini
    keys (``GEMINI_API_KEYS``, separated by a comma). Every key has its own
    quota, so several keys mean:

    * more room - the board keeps working while one key is busy,
    * a fallback **inside Gemini** - when a key runs out (or is refused),
      the next one is tried at once, without any waiting.

    The fallback stays in Gemini on purpose: the OCR of the board needs a
    model that reads a picture, and the answers of the two services must
    have the same shape. A second model would only be a second thing that
    can go wrong.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        mock: bool | None = None,
        api_keys: Sequence[str] | None = None,
    ) -> None:
        settings = get_settings()
        if api_keys is not None:
            self.api_keys: tuple[str, ...] = tuple(
                key.strip() for key in api_keys if key and key.strip()
            )
        elif api_key is not None:
            self.api_keys = (api_key.strip(),) if api_key.strip() else ()
        else:
            self.api_keys = settings.all_gemini_keys
        self.api_key = self.api_keys[0] if self.api_keys else ""
        self.model = model or settings.gemini_model
        self.mock = settings.mock_llm if mock is None else mock
        self._clients: dict[str, Any] = {}

    # ------------------------------------------------------------------ api
    @property
    def available(self) -> bool:
        """``True`` when a real call is possible."""
        return bool(self.api_keys) and not self.mock

    @property
    def key_count(self) -> int:
        """How many keys the service knows."""
        return len(self.api_keys)

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
            repaired = self._call_with_retries(
                render_prompt(REPAIR_PROMPT, broken=answer), None, mime_type
            )
            return extract_json(repaired)

    # ------------------------------------------------------------ internals
    def _client_or_create(self, key: str) -> Any:
        """The client of one key (one client per key)."""
        client = self._clients.get(key)
        if client is None:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - the SDK is optional
                raise CloudError("The google-genai package is not installed") from exc
            client = genai.Client(api_key=key)
            self._clients[key] = client
        return client

    def _call_with_retries(self, prompt: str, image_bytes: bytes | None, mime_type: str) -> str:
        """One request - every key is tried, then the whole list again.

        With one key this is the old behaviour: three tries with an
        exponential backoff. With several keys a key that fails (its quota
        is gone, it is refused) is **skipped at once** - the next key
        answers without any waiting.

        A key that is *refused* (a wrong key) is taken out of the list -
        waiting would not help it. A **temporary** failure ("503
        UNAVAILABLE", a timeout) is tried again with a backoff, and the
        last failure is reported in a way the teacher understands.
        """
        keys = list(self.api_keys)
        if not keys:
            raise CloudError("No Gemini API key is configured")
        last_error: Exception | None = None
        refused: set[str] = set()
        for round_index in range(MAX_RETRIES + 1):
            for index, key in enumerate(keys):
                if key in refused:
                    continue
                try:
                    return self._call_once(prompt, image_bytes, mime_type, key)
                except Exception as exc:  # noqa: BLE001 - the SDK raises many types
                    last_error = exc
                    if is_transient(exc):
                        LOGGER.warning(
                            "Gemini is busy (key %d of %d): %s", index + 1, len(keys), exc
                        )
                    else:
                        LOGGER.warning(
                            "The key %d of %d was refused: %s", index + 1, len(keys), exc
                        )
                        refused.add(key)
            if round_index < MAX_RETRIES:
                delay = min(BACKOFF_MAX, BACKOFF_BASE * (2**round_index))
                LOGGER.warning("Every key failed - waiting %.1fs", delay)
                time.sleep(delay)
        raise CloudError(
            describe_failure(last_error) if last_error else "Gemini could not be reached"
        )

    def _call_once(
        self, prompt: str, image_bytes: bytes | None, mime_type: str, key: str = ""
    ) -> str:
        from google.genai import types

        client = self._client_or_create(key or self.api_key)
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
    "BACKOFF_MAX",
    "MAX_RETRIES",
    "PERMANENT_MARKERS",
    "TRANSIENT_MARKERS",
    "MOCK_EXPLAIN",
    "MOCK_OCR",
    "MOCK_WORDPROBLEM",
    "GeminiService",
    "describe_failure",
    "extract_json",
    "is_transient",
]
