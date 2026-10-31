"""The OCR package.

* :mod:`aieva.core.ocr.preprocess` - the image pre-processing (Pillow / NumPy).
* :mod:`aieva.core.ocr.engines` - the OCR engines (Gemini, manual, mock).
* :mod:`aieva.core.ocr.pipeline` - the pipeline that validates with SymPy.
* :mod:`aieva.core.ocr.worker` - the background worker / service.
* :mod:`aieva.core.ocr.capture` - the screen capture sources.
* :mod:`aieva.core.ocr.region_selector` - the Kivy region selection overlay.
"""

from aieva.core.ocr.engines import (
    GeminiOcr,
    ManualOcr,
    MockOcr,
    OcrEngine,
    OcrResult,
    Pix2TextOcr,
)
from aieva.core.ocr.pipeline import OcrPipeline
from aieva.core.ocr.preprocess import PreprocessOptions, image_hash, preprocess

__all__ = [
    "GeminiOcr",
    "ManualOcr",
    "MockOcr",
    "OcrEngine",
    "OcrPipeline",
    "OcrResult",
    "Pix2TextOcr",
    "PreprocessOptions",
    "image_hash",
    "preprocess",
]
