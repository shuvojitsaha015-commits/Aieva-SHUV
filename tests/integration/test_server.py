"""Phase 8: the Aieva fog server."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server.main import RateLimiter, create_app
from server.services.gemini import GeminiService, extract_json


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    """A client of a server without an API key (the mock answers)."""
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("AIEVA_MOCK_LLM", "true")
    monkeypatch.delenv("AIEVA_SERVER_KEY", raising=False)
    from aieva.config import get_settings

    get_settings(reload=True)
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings(reload=True)


def _image_bytes(size: tuple[int, int] = (40, 20)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


# --------------------------------------------------------------------- health
def test_the_root_shows_the_map_of_the_server(client: TestClient) -> None:
    """The address that is opened by hand answers with a short map."""
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Aieva fog server"
    assert payload["mode"] == "mock"
    assert payload["endpoints"]["health"] == "/health"


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mock"] is True


# ------------------------------------------------------------------------ ocr
def test_ocr_answers_in_mock_mode(client: TestClient) -> None:
    response = client.post(
        "/api/math/ocr", files={"image": ("capture.png", _image_bytes(), "image/png")}
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"latex", "plain", "confidence_note", "kind", "intent", "chart"}
    assert payload["plain"]


def test_ocr_rejects_an_empty_image(client: TestClient) -> None:
    response = client.post("/api/math/ocr", files={"image": ("empty.png", b"", "image/png")})
    assert response.status_code == 400


def test_ocr_rejects_a_huge_image(client: TestClient) -> None:
    payload = b"x" * (5 * 1024 * 1024 + 10)
    response = client.post("/api/math/ocr", files={"image": ("big.png", payload, "image/png")})
    assert response.status_code == 413


def test_ocr_uses_the_model_answer(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("AIEVA_MOCK_LLM", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from aieva.config import get_settings

    get_settings(reload=True)

    def fake_call(self, prompt: str, image_bytes=None, mime_type="image/png") -> str:
        return '{"latex": "y = x^2", "plain": "y = x**2", "confidence_note": "sure", "kind": "equation"}'

    monkeypatch.setattr(GeminiService, "_call_with_retries", fake_call)
    with TestClient(create_app()) as fresh:
        response = fresh.post(
            "/api/math/ocr", files={"image": ("capture.png", _image_bytes(), "image/png")}
        )
    assert response.status_code == 200
    assert response.json()["plain"] == "y = x**2"
    get_settings(reload=True)


# --------------------------------------------------------------------- explain
def test_explain_answers_in_mock_mode(client: TestClient) -> None:
    response = client.post(
        "/api/math/explain",
        json={"problem_latex": "x^2 + 3x - 2 = 0", "sympy_answer": "x = 1", "hints": ""},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["steps"]
    assert payload["steps"][0]["title"]


def test_explain_rejects_a_long_text(client: TestClient) -> None:
    response = client.post(
        "/api/math/explain",
        json={"problem_latex": "x" * 5000, "sympy_answer": "1", "hints": ""},
    )
    assert response.status_code == 422


# ----------------------------------------------------------------- wordproblem
def test_wordproblem_answers_in_mock_mode(client: TestClient) -> None:
    response = client.post(
        "/api/math/wordproblem",
        json={"text": "A ball is thrown with 20 m/s at 45 degrees."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["problem_type"] == "kinematic_projectile"
    assert payload["variables"]
    assert payload["equations"]


def test_wordproblem_rejects_an_empty_text(client: TestClient) -> None:
    response = client.post("/api/math/wordproblem", json={"text": "   "})
    assert response.status_code == 400


# ------------------------------------------------------------------- security
def test_the_api_key_is_required(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("AIEVA_SERVER_KEY", "secret")
    from aieva.config import get_settings

    get_settings(reload=True)
    with TestClient(create_app()) as guarded:
        response = guarded.post("/api/math/wordproblem", json={"text": "hello"})
        assert response.status_code == 401
        allowed = guarded.post(
            "/api/math/wordproblem", json={"text": "hello"}, headers={"X-Aieva-Key": "secret"}
        )
        assert allowed.status_code == 200
    get_settings(reload=True)


def test_the_rate_limit_works() -> None:
    limiter = RateLimiter(limit=3, window_seconds=60)
    for _ in range(3):
        assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False
    assert limiter.allow("5.6.7.8") is True
    limiter.reset()
    assert limiter.allow("1.2.3.4") is True


def test_the_rate_limit_answers_with_429(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AIEVA_CACHE_DIR", str(tmp_path / "cache"))
    from aieva.config import get_settings

    get_settings(reload=True)
    application = create_app()
    application.state.limiter = RateLimiter(limit=1, window_seconds=60)
    with TestClient(application) as limited:
        first = limited.post("/api/math/wordproblem", json={"text": "one"})
        second = limited.post("/api/math/wordproblem", json={"text": "two"})
    assert first.status_code == 200
    assert second.status_code == 429
    get_settings(reload=True)


# ------------------------------------------------------------------- the LLM
def test_extract_json_reads_plain_json() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_reads_a_fenced_answer() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_reads_json_inside_a_text() -> None:
    assert extract_json('Here you are: {"a": 1} - done') == {"a": 1}


def test_extract_json_rejects_garbage() -> None:
    from aieva.core.errors import CloudError

    with pytest.raises(CloudError):
        extract_json("no json here")


def test_the_service_retries(monkeypatch) -> None:
    calls = {"count": 0}

    def failing(self, prompt, image_bytes=None, mime_type="image/png", key=""):
        calls["count"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(GeminiService, "_call_once", failing)
    service = GeminiService(api_key="key", mock=False)
    monkeypatch.setattr("server.services.gemini.time.sleep", lambda _s: None)
    from aieva.core.errors import CloudError

    with pytest.raises(CloudError):
        service.complete_json("prompt")
    assert calls["count"] == 3  # the first attempt plus two retries
