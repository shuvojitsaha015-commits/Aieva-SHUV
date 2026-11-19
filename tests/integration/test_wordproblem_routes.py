"""The routes of the server must not break on the JSON braces.

The prompts of Aieva show the wanted JSON to the model::

    {
      "problem_type": "kinematic_projectile"
    }

The old code filled the placeholders with ``str.format`` - and the
server died with::

    KeyError: '\\n  "problem_type"'

The safe renderer (:func:`aieva.core.llm.prompts.render_prompt`) fills
the placeholders without touching the JSON body. These tests call the
routes **with a real key configured** (the model is mocked, but the
prompt is built for real) - that is the path that was broken.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.main import create_app
from server.services.gemini import GeminiService


@pytest.fixture
def live_client(monkeypatch, tmp_path) -> TestClient:
    """A client with a key - the model is mocked, the prompt is real."""
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("AIEVA_MOCK_LLM", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("AIEVA_SERVER_KEY", raising=False)
    from aieva.config import get_settings

    get_settings(reload=True)
    with TestClient(create_app()) as client:
        yield client
    get_settings(reload=True)


@pytest.fixture
def prompts(monkeypatch) -> list[str]:
    """Every prompt that is sent to the model."""
    sent: list[str] = []

    def fake_call(self, prompt: str, image_bytes=None, mime_type="image/png") -> str:
        sent.append(prompt)
        return '{"problem_type": "kinematic_projectile", "variables": []}'

    monkeypatch.setattr(GeminiService, "_call_with_retries", fake_call)
    return sent


# ------------------------------------------------------------- the word problem
def test_the_word_problem_works_with_a_real_key(live_client: TestClient, prompts) -> None:
    """The route that died with a KeyError must answer now."""
    response = live_client.post(
        "/api/math/wordproblem",
        json={"text": "A ball is thrown with 20 m/s at 45 degrees."},
    )
    assert response.status_code == 200
    assert response.json()["problem_type"] == "kinematic_projectile"


def test_the_sent_prompt_has_the_problem_and_the_json(live_client: TestClient, prompts) -> None:
    live_client.post(
        "/api/math/wordproblem",
        json={"text": "A ball is thrown with 20 m/s at 45 degrees."},
    )
    assert len(prompts) == 1
    prompt = prompts[0]
    assert "A ball is thrown with 20 m/s" in prompt
    assert '"problem_type"' in prompt
    assert "{" in prompt and "}" in prompt


# ------------------------------------------------------------------- explain
def test_the_explain_works_with_a_real_key(live_client: TestClient, monkeypatch) -> None:
    """The second route with JSON braces must answer too."""
    monkeypatch.setattr(
        GeminiService,
        "_call_with_retries",
        lambda self, prompt, image_bytes=None, mime_type="image/png": (
            '{"steps": [{"title": "t", "explanation": "e", "latex": "x"}]}'
        ),
    )
    response = live_client.post(
        "/api/math/explain",
        json={"problem_latex": "x^2 + 3x - 2 = 0", "sympy_answer": "x = 1", "hints": ""},
    )
    assert response.status_code == 200
    assert response.json()["steps"][0]["title"] == "t"


def test_the_sent_prompt_of_the_explain_has_the_json(live_client: TestClient, monkeypatch) -> None:
    sent: list[str] = []

    def fake_call(self, prompt: str, image_bytes=None, mime_type="image/png") -> str:
        sent.append(prompt)
        return '{"steps": [{"title": "t", "explanation": "e", "latex": "x"}]}'

    monkeypatch.setattr(GeminiService, "_call_with_retries", fake_call)
    live_client.post(
        "/api/math/explain",
        json={"problem_latex": "x^2", "sympy_answer": "2", "hints": "none"},
    )
    assert len(sent) == 1
    assert '"steps"' in sent[0]
    assert "x^2" in sent[0]


# --------------------------------------------------------------------- ocr
def test_the_ocr_works_with_a_real_key(live_client: TestClient, monkeypatch) -> None:
    """The OCR prompt is full of braces as well."""
    import io

    from PIL import Image

    monkeypatch.setattr(
        GeminiService,
        "_call_with_retries",
        lambda self, prompt, image_bytes=None, mime_type="image/png": (
            '{"latex": "y = x^2", "plain": "y = x**2", "confidence_note": "sure", '
            '"kind": "equation", "intent": "solve"}'
        ),
    )
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buffer, format="PNG")
    response = live_client.post(
        "/api/math/ocr", files={"image": ("capture.png", buffer.getvalue(), "image/png")}
    )
    assert response.status_code == 200
    assert response.json()["plain"] == "y = x**2"
