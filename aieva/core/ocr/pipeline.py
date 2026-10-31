"""The OCR pipeline.

``OcrPipeline.run(image)``:

1. pre-process the image (grayscale, deskew, denoise, threshold, crop, upscale)
2. try the engines in the configured order
3. validate every answer with the LaTeX / text parser - if SymPy cannot read
   it, the next engine is tried
4. if nothing works, return a result with ``needs_manual_input`` - the UI
   turns that into an editable text box prefilled with the best guess

The results are cached by the hash of the image, so the same capture is only
read once.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from PIL import Image

from aieva.core.cache import DiskCache
from aieva.core.ocr.engines import OcrEngine, OcrResult
from aieva.core.ocr.preprocess import PreprocessOptions, image_hash, preprocess
from aieva.core.timing import timed

LOGGER = logging.getLogger(__name__)

#: The cache namespace of the OCR results.
CACHE_NAMESPACE = "ocr"

#: A text only counts as mathematics when it has a number, an operator or a
#: function in it - otherwise every word would be a product of letters.
_MEANINGFUL_RE = re.compile(
    r"[0-9]|[+\-*/^()]|\b(sin|cos|tan|cot|sec|csc|asin|acos|atan|sinh|cosh|tanh"
    r"|exp|log|ln|sqrt|abs|pi|e)\b"
)


def looks_like_math(text: str) -> bool:
    """``True`` when the text can be a formula (and not a sentence)."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    if re.fullmatch(r"[A-Za-z]", stripped):
        return True
    return bool(_MEANINGFUL_RE.search(stripped))


class OcrPipeline:
    """Runs the engines until one of them produces something SymPy can read."""

    def __init__(
        self,
        engines: Sequence[OcrEngine] | None = None,
        cache: DiskCache | None = None,
        preprocess_options: PreprocessOptions | None = None,
        use_cache: bool = True,
    ) -> None:
        if engines is None:
            from aieva.core.ocr.engines import GeminiOcr, ManualOcr

            engines = [GeminiOcr(), ManualOcr()]
        self.engines: list[OcrEngine] = list(engines)
        self.cache = cache if cache is not None else DiskCache()
        self.options = preprocess_options or PreprocessOptions()
        self.use_cache = use_cache

    # ------------------------------------------------------------------ api
    def run(self, image: Image.Image, use_cache: bool | None = None) -> OcrResult:
        """Read the mathematics of a picture (the timing is logged)."""
        with timed("the OCR"):
            return self._run(image, use_cache=use_cache)

    def _run(self, image: Image.Image, use_cache: bool | None = None) -> OcrResult:
        """Read the image and return the best result."""
        use_cache = self.use_cache if use_cache is None else use_cache
        key = image_hash(image)
        if use_cache:
            cached = self.cache.get(CACHE_NAMESPACE, key)
            if cached:
                LOGGER.debug("OCR cache hit for %s", key[:12])
                return OcrResult.from_dict(cached)

        prepared = preprocess(image, self.options)
        best: OcrResult | None = None
        errors: list[str] = []

        for engine in self.engines:
            if not engine.available():
                continue
            try:
                result = engine.recognize(prepared)
            except Exception as exc:  # noqa: BLE001 - an engine may be unavailable
                LOGGER.warning("OCR engine %s failed: %s", engine.name, exc)
                errors.append(f"{engine.name}: {exc}")
                continue
            if result.is_empty:
                continue
            if best is None:
                best = result
            if self._is_valid(result):
                result.engine = result.engine or engine.name
                if use_cache:
                    self.cache.set(CACHE_NAMESPACE, key, result.to_dict())
                return result

        if best is not None:
            # nothing could be parsed - the user has to confirm the guess
            best.needs_manual_input = True
            best.confidence_note = (best.confidence_note + " " if best.confidence_note else "") + (
                "SymPy could not parse the answer - please check it."
            )
            if use_cache:
                self.cache.set(CACHE_NAMESPACE, key, best.to_dict())
            return best

        note = "No OCR engine could read the image."
        if errors:
            note += " " + " | ".join(errors)
        return OcrResult(
            latex="",
            plain="",
            confidence_note=note,
            kind="unknown",
            engine="none",
            needs_manual_input=True,
        )

    # ------------------------------------------------------------ internals
    @staticmethod
    def _is_valid(result: OcrResult) -> bool:
        """Can SymPy read the answer?"""
        from aieva.core.latex_adapter import latex_to_equation, latex_to_sympy
        from aieva.core.safe_parse import parse_equation, parse_text_expression

        for text, is_latex in ((result.latex, True), (result.plain, False)):
            text = (text or "").strip()
            if not text or not looks_like_math(text):
                continue
            try:
                if is_latex:
                    if "=" in text:
                        latex_to_equation(text)
                    else:
                        latex_to_sympy(text)
                else:
                    if "=" in text:
                        parse_equation(text)
                    else:
                        parse_text_expression(text)
                return True
            except Exception:  # noqa: BLE001 - any parse problem means "not valid"
                continue
        return False


__all__ = ["CACHE_NAMESPACE", "OcrPipeline"]
