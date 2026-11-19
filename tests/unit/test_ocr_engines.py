"""The order of the OCR engines and the cooling time after a failure."""

from __future__ import annotations

from PIL import Image

from aieva.core.ocr.engines import OcrEngine, OcrResult, default_engines
from aieva.core.ocr.pipeline import OcrPipeline


class FakeEngine(OcrEngine):
    """An engine that says what the test wants."""

    name = "fake"

    def __init__(self, name: str, text: str = "", fail: bool = False) -> None:
        self.name = name
        self.text = text
        self.fail = fail
        self.calls = 0

    def available(self) -> bool:
        return True

    def recognize(self, image: Image.Image) -> OcrResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("the engine is broken")
        return OcrResult(latex=self.text, plain=self.text, engine=self.name)


def _image() -> Image.Image:
    return Image.new("RGB", (60, 40), "white")


def test_gemini_is_the_engine_of_the_board() -> None:
    names = [engine.name for engine in default_engines()]
    assert names == ["gemini"]


def test_the_first_engine_that_can_be_read_wins() -> None:
    good = FakeEngine("good", "x = 2")
    later = FakeEngine("later", "y = 3")
    pipeline = OcrPipeline(engines=[good, later], use_cache=False)
    result = pipeline.run(_image())
    assert result.engine == "good"
    assert later.calls == 0


def test_the_next_engine_is_used_when_the_first_one_fails() -> None:
    broken = FakeEngine("broken", fail=True)
    good = FakeEngine("good", "x = 2")
    pipeline = OcrPipeline(engines=[broken, good], use_cache=False)
    result = pipeline.run(_image())
    assert result.engine == "good"
    assert broken.calls == 1


def test_a_broken_engine_is_skipped_after_a_failure() -> None:
    broken = FakeEngine("broken", fail=True)
    good = FakeEngine("good", "x = 2")
    pipeline = OcrPipeline(engines=[broken, good], use_cache=False)
    pipeline.run(_image())
    pipeline.run(_image())
    # the broken engine is in its cooling time - it is not asked a second time
    assert broken.calls == 1


def test_the_cooling_time_can_be_switched_off() -> None:
    broken = FakeEngine("broken", fail=True)
    good = FakeEngine("good", "x = 2")
    pipeline = OcrPipeline(engines=[broken, good], use_cache=False, engine_cooldown=0.0)
    pipeline.run(_image())
    pipeline.run(_image())
    assert broken.calls == 2


def test_the_reading_is_normalised() -> None:
    engine = FakeEngine("local", "x² + 1")
    pipeline = OcrPipeline(engines=[engine], use_cache=False)
    result = pipeline.run(_image())
    assert "**2" in result.latex


def test_without_any_engine_the_user_has_to_confirm() -> None:
    engine = FakeEngine("empty", "")
    pipeline = OcrPipeline(engines=[engine], use_cache=False)
    result = pipeline.run(_image())
    assert result.needs_manual_input is True
    assert result.engine == "none"
