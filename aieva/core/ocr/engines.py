"""The OCR engines.

An engine turns an image into an :class:`OcrResult`. The engines are tried in
the configured order and the first result that SymPy can parse wins - see
:mod:`aieva.core.ocr.pipeline`.

Engines shipped in v1:

* :class:`GeminiOcr` - asks the fog server (Gemini Vision) for the LaTeX.
  **This is the engine of Aieva** - Gemini reads the board.
* :class:`ManualOcr` - the user types the expression (the escape hatch).
* :class:`MockOcr` - canned answers, used by the tests.
"""

from __future__ import annotations

import io
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from PIL import Image

from aieva.core.errors import OcrError

#: The kinds of content the OCR can report.
RESULT_KINDS = ("expression", "equation", "text", "unknown")

#: What should be done with the problem the model read.
#:
#: ``solve`` - the answer is wanted, ``graph`` - the picture is wanted,
#: ``both`` - the answer *and* the picture, ``none`` - there is no
#: mathematics on the board.
INTENTS = ("solve", "graph", "both", "none")


@dataclass
class OcrResult:
    """What an OCR engine found."""

    latex: str = ""
    plain: str = ""
    confidence_note: str = ""
    kind: str = "unknown"
    engine: str = ""
    #: What should be done with the problem (``""`` when the model did not say).
    intent: str = ""
    #: The table of values the model read (``None`` when there is no table).
    chart: dict[str, Any] | None = None
    #: ``True`` when the user has to confirm / correct the result.
    needs_manual_input: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.latex.strip() and not self.plain.strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> OcrResult:
        known = {
            key: payload.get(key)
            for key in (
                "latex",
                "plain",
                "confidence_note",
                "kind",
                "engine",
                "intent",
                "needs_manual_input",
            )
        }
        known["raw"] = payload.get("raw") or {}
        chart = payload.get("chart")
        known["chart"] = chart if isinstance(chart, dict) else None
        return cls(**known)  # type: ignore[arg-type]


class OcrEngine(ABC):
    """The interface every OCR engine implements."""

    #: The name that is shown in the UI and in the logs.
    name: str = "engine"

    @abstractmethod
    def recognize(self, image: Image.Image) -> OcrResult:
        """Read the image and return the result."""

    def available(self) -> bool:
        """``True`` when the engine can run right now."""
        return True

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<{type(self).__name__} name={self.name!r}>"


class MockOcr(OcrEngine):
    """Returns a canned answer - used by the tests and the offline demo."""

    name = "mock"

    def __init__(
        self, latex: str = "x**2 + y**2 = 9", plain: str = "x**2 + y**2 = 9", kind: str = "equation"
    ) -> None:
        self.latex = latex
        self.plain = plain
        self.kind = kind

    def recognize(self, image: Image.Image) -> OcrResult:
        return OcrResult(
            latex=self.latex,
            plain=self.plain,
            confidence_note="mock engine - the answer is canned",
            kind=self.kind,
            engine=self.name,
            raw={"size": list(image.size)},
        )


class ManualOcr(OcrEngine):
    """The user types the expression (the escape hatch of the pipeline)."""

    name = "manual"

    def __init__(self, text: str = "") -> None:
        self.text = text

    def recognize(self, image: Image.Image) -> OcrResult:
        text = self.text.strip()
        return OcrResult(
            latex=text,
            plain=text,
            confidence_note="typed by the user",
            kind="expression" if "=" not in text else "equation",
            engine=self.name,
            needs_manual_input=not text,
        )


class GeminiOcr(OcrEngine):
    """Reads the image through the fog server (Gemini Vision)."""

    name = "gemini"

    def __init__(self, server_url: str = "", api_key: str = "", timeout: float = 30.0) -> None:
        from aieva.config import get_settings

        settings = get_settings()
        self.server_url = (server_url or settings.server_url).rstrip("/")
        self.api_key = api_key or settings.server_api_key
        self.timeout = timeout or settings.server_timeout

    def available(self) -> bool:
        return bool(self.server_url)

    def recognize(self, image: Image.Image) -> OcrResult:
        if not self.server_url:
            raise OcrError("No OCR server configured")
        import httpx

        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        headers = {"X-Aieva-Key": self.api_key} if self.api_key else {}
        try:
            response = httpx.post(
                f"{self.server_url}/api/math/ocr",
                files={"image": ("capture.png", buffer.getvalue(), "image/png")},
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:  # pragma: no cover - network error
            raise OcrError(f"The OCR server could not be reached: {exc}") from exc
        except json.JSONDecodeError as exc:  # pragma: no cover - bad answer
            raise OcrError("The OCR server sent an answer that is not JSON") from exc
        return OcrResult(
            latex=payload.get("latex", ""),
            plain=payload.get("plain", ""),
            confidence_note=payload.get("confidence_note", ""),
            kind=payload.get("kind", "unknown"),
            engine=self.name,
            intent=str(payload.get("intent", "") or "").strip().lower(),
            chart=_chart_of(payload.get("chart")),
            raw=payload,
        )


def _chart_of(value: Any) -> dict[str, Any] | None:
    """The table of values the model read (``None`` when there is none)."""
    if not isinstance(value, dict):
        return None
    from aieva.core.charts import ChartData

    data = ChartData.from_dict(value)
    return None if data.is_empty() else data.to_dict()


def default_engines() -> list[OcrEngine]:
    """The engines of the board.

    **Gemini is the core of Aieva.** The board is read through the fog
    server (the network is needed - there is no offline version), and the
    answer is checked with SymPy before it is shown.

    The list exists so that a second engine can be added later without
    changing the pipeline.
    """
    return [GeminiOcr()]


__all__ = [
    "INTENTS",
    "GeminiOcr",
    "ManualOcr",
    "MockOcr",
    "OcrEngine",
    "OcrResult",
    "RESULT_KINDS",
    "default_engines",
]
