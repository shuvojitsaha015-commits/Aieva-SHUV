"""Phase 8: the OCR pre-processing, the engines and the pipeline."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw

from aieva.core.ocr.engines import ManualOcr, MockOcr, OcrResult
from aieva.core.ocr.pipeline import OcrPipeline
from aieva.core.ocr.preprocess import (
    PreprocessOptions,
    adaptive_threshold,
    autocrop,
    denoise,
    deskew,
    estimate_skew,
    image_hash,
    preprocess,
    upscale,
)


@pytest.fixture
def equation_image() -> Image.Image:
    """A picture with a formula written on it."""
    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 80), "y = x^2 + 3x", fill="black")
    return image


@pytest.fixture(autouse=True)
def _cache(tmp_path, monkeypatch):
    """Every test uses its own cache directory."""
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    from aieva.config import get_settings

    get_settings(reload=True)
    yield
    get_settings(reload=True)


# ------------------------------------------------------------- pre-processing
def test_preprocess_keeps_the_size(equation_image: Image.Image) -> None:
    result = preprocess(equation_image)
    assert result.width > 0 and result.height > 0


def test_preprocess_removes_the_empty_border(equation_image: Image.Image) -> None:
    cropped = autocrop(equation_image)
    assert cropped.width <= equation_image.width
    assert cropped.height <= equation_image.height


def test_upscale_enlarges_a_small_image() -> None:
    small = Image.new("RGB", (40, 20), "white")
    big = upscale(small, target_width=320)
    assert big.width == 320


def test_upscale_leaves_a_big_image_alone(equation_image: Image.Image) -> None:
    assert upscale(equation_image, target_width=320).width == equation_image.width


def test_adaptive_threshold_makes_the_image_binary() -> None:
    array = np.full((40, 40), 200, dtype=np.uint8)
    array[10:20, 10:20] = 10
    result = adaptive_threshold(Image.fromarray(array), window=9, offset=5)
    values = set(np.unique(np.asarray(result)).tolist())
    assert values <= {0, 255}


def test_denoise_keeps_the_shape() -> None:
    array = np.full((30, 30), 255, dtype=np.uint8)
    array[10:20, 10:20] = 0
    result = denoise(Image.fromarray(array))
    assert result.size == (30, 30)


def test_deskew_of_a_straight_image_does_nothing(equation_image: Image.Image) -> None:
    assert abs(estimate_skew(np.asarray(equation_image.convert("L")))) < 5.0
    assert deskew(equation_image).size == equation_image.size


def test_image_hash_is_stable(equation_image: Image.Image) -> None:
    assert image_hash(equation_image) == image_hash(equation_image.copy())
    other = Image.new("RGB", (600, 200), "black")
    assert image_hash(equation_image) != image_hash(other)


def test_preprocess_options_are_used(equation_image: Image.Image) -> None:
    options = PreprocessOptions(keep_color=False)
    result = preprocess(equation_image, options)
    assert result.mode in ("L", "RGB")


# ------------------------------------------------------------------- engines
def test_mock_engine_answers() -> None:
    result = MockOcr(latex="x^2", plain="x**2").recognize(Image.new("RGB", (10, 10)))
    assert result.plain == "x**2"
    assert result.engine == "mock"


def test_manual_engine_uses_the_typed_text() -> None:
    result = ManualOcr("x + 1").recognize(Image.new("RGB", (10, 10)))
    assert result.plain == "x + 1"
    assert result.needs_manual_input is False


def test_empty_manual_engine_asks_for_manual_input() -> None:
    result = ManualOcr("").recognize(Image.new("RGB", (10, 10)))
    assert result.needs_manual_input is True


# ------------------------------------------------------------------ pipeline
def test_pipeline_accepts_a_valid_answer(equation_image: Image.Image) -> None:
    pipeline = OcrPipeline(engines=[MockOcr(latex="x^2", plain="x**2")])
    result = pipeline.run(equation_image)
    assert result.needs_manual_input is False
    assert result.plain == "x**2"


def test_pipeline_asks_for_manual_input_when_nothing_parses(
    equation_image: Image.Image,
) -> None:
    pipeline = OcrPipeline(engines=[MockOcr(latex="\\not maths", plain="??")])
    result = pipeline.run(equation_image)
    assert result.needs_manual_input is True
    assert "check it" in result.confidence_note


def test_pipeline_tries_the_next_engine(equation_image: Image.Image) -> None:
    pipeline = OcrPipeline(
        engines=[
            MockOcr(latex="???", plain="???"),
            MockOcr(latex="x^2", plain="x**2"),
        ]
    )
    result = pipeline.run(equation_image)
    assert result.plain == "x**2"
    assert result.needs_manual_input is False


def test_pipeline_returns_manual_input_when_no_engine_works(
    equation_image: Image.Image,
) -> None:
    pipeline = OcrPipeline(engines=[ManualOcr("")])
    result = pipeline.run(equation_image)
    assert result.needs_manual_input is True
    assert result.is_empty


def test_pipeline_caches_the_result(equation_image: Image.Image) -> None:
    calls = {"count": 0}

    class CountingEngine(MockOcr):
        def recognize(self, image: Image.Image) -> OcrResult:
            calls["count"] += 1
            return super().recognize(image)

    pipeline = OcrPipeline(engines=[CountingEngine(latex="x^2", plain="x**2")])
    pipeline.run(equation_image)
    pipeline.run(equation_image)
    assert calls["count"] == 1


def test_pipeline_validates_latex(equation_image: Image.Image) -> None:
    pipeline = OcrPipeline(engines=[MockOcr(latex="x^2 + 1", plain="")])
    result = pipeline.run(equation_image)
    assert result.needs_manual_input is False
