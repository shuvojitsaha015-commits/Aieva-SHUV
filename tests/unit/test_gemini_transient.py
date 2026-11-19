"""What happens when Gemini is busy, slow or refuses the key.

The teacher must never see a frozen board. A call to Google can fail in
three ways, and each one has its own answer:

* **The service is busy** ("503 UNAVAILABLE") or the network hiccuped
  (a timeout) - the call is simply tried again, with a backoff.
* **The key is refused** ("401", "403") - waiting does not help, so the
  key is left out and the next one answers at once.
* **The key works but the answer is broken** - the repair prompt asks
  the model once more.

In every case the last failure ends as a :class:`CloudError` - the
server never crashes and the teacher gets a clear message.
"""

from __future__ import annotations

import pytest

from aieva.core.errors import CloudError
from server.services.gemini import (
    BACKOFF_BASE,
    MAX_RETRIES,
    GeminiService,
    describe_failure,
    is_transient,
)


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    """The tests must not wait for the real backoff."""
    monkeypatch.setattr("server.services.gemini.time.sleep", lambda _s: None)


# ------------------------------------------------------------- the helpers
@pytest.mark.parametrize(
    "message",
    [
        "503 UNAVAILABLE: The service is currently unavailable.",
        "429 RESOURCE_EXHAUSTED: Quota exceeded",
        "Deadline exceeded after 120s",
        "Read timed out",
        "Connection reset by peer",
        "502 Bad Gateway",
        "504 Gateway Timeout",
        "The service is overloaded",
    ],
)
def test_a_busy_service_is_transient(message: str) -> None:
    assert is_transient(RuntimeError(message)) is True


@pytest.mark.parametrize(
    "message",
    [
        "400 INVALID_ARGUMENT: bad request",
        "401 UNAUTHENTICATED: the API key is not valid",
        "403 PERMISSION_DENIED: the key may not do that",
        "API_KEY_INVALID",
    ],
)
def test_a_refused_key_is_not_transient(message: str) -> None:
    assert is_transient(RuntimeError(message)) is False


def test_an_unknown_error_is_still_tried_again() -> None:
    """The old behaviour was to try again - it must not get worse."""
    assert is_transient(RuntimeError("boom")) is True


def test_the_message_of_a_busy_service_is_friendly() -> None:
    text = describe_failure(RuntimeError("503 UNAVAILABLE"))
    assert "temporarily unavailable" in text
    assert "503" in text


def test_the_message_of_a_refused_key_points_to_the_key() -> None:
    text = describe_failure(RuntimeError("401 UNAUTHENTICATED"))
    assert "API key" in text


# ------------------------------------------------------------------ the retry
def test_a_503_is_tried_again_and_then_works(monkeypatch) -> None:
    """The service was busy twice - the third try answers."""
    calls: list[int] = []

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("503 UNAVAILABLE: The model is overloaded")
            return '{"latex": "x = 2"}'

    service = Service(api_keys=["key"], mock=False)
    answer = service.complete_json("the prompt")
    assert answer == {"latex": "x = 2"}
    assert len(calls) == 3


def test_a_timeout_is_tried_again(monkeypatch) -> None:
    calls: list[int] = []

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            calls.append(1)
            if len(calls) < 2:
                raise TimeoutError("Read timed out. (read timeout=120)")
            return '{"latex": "x = 2"}'

    service = Service(api_keys=["key"], mock=False)
    assert service.complete_json("the prompt") == {"latex": "x = 2"}
    assert len(calls) == 2


def test_the_backoff_grows_between_the_rounds(monkeypatch) -> None:
    """The wait doubles every round - the service needs time."""
    waits: list[float] = []
    monkeypatch.setattr("server.services.gemini.time.sleep", waits.append)

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            raise RuntimeError("503 UNAVAILABLE")

    service = Service(api_keys=["key"], mock=False)
    with pytest.raises(CloudError):
        service.complete_json("the prompt")

    assert waits == [BACKOFF_BASE, BACKOFF_BASE * 2]
    assert len(waits) == MAX_RETRIES


def test_a_503_that_never_ends_becomes_a_cloud_error(monkeypatch) -> None:
    """After the last try the teacher gets a clear message."""
    calls: list[int] = []

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            calls.append(1)
            raise RuntimeError("503 UNAVAILABLE: The service is currently unavailable")

    service = Service(api_keys=["key"], mock=False)
    with pytest.raises(CloudError) as error:
        service.complete_json("the prompt")

    assert len(calls) == MAX_RETRIES + 1
    assert "temporarily unavailable" in str(error.value)


def test_a_timeout_that_never_ends_becomes_a_cloud_error(monkeypatch) -> None:
    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            raise TimeoutError("Read timed out. (read timeout=120)")

    service = Service(api_keys=["key"], mock=False)
    with pytest.raises(CloudError):
        service.complete_json("the prompt")


def test_a_refused_key_is_not_tried_again(monkeypatch) -> None:
    """Waiting does not help a wrong key - it is left out at once."""
    calls: list[str] = []

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            calls.append(key)
            if key == "wrong":
                raise RuntimeError("400 INVALID_ARGUMENT: the API key is not valid")
            return '{"latex": "x = 2"}'

    service = Service(api_keys=["wrong", "good"], mock=False)
    assert service.complete_json("the prompt") == {"latex": "x = 2"}
    # the wrong key is asked exactly once - the good one answers at once
    assert calls == ["wrong", "good"]


def test_a_refused_key_alone_ends_quickly(monkeypatch) -> None:
    """A wrong key must not make the teacher wait for the backoff."""
    calls: list[int] = []

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            calls.append(1)
            raise RuntimeError("401 UNAUTHENTICATED: the API key is not valid")

    service = Service(api_keys=["key"], mock=False)
    with pytest.raises(CloudError) as error:
        service.complete_json("the prompt")
    assert len(calls) == 1
    assert "API key" in str(error.value)


def test_the_broken_answer_is_repaired_once(monkeypatch) -> None:
    """The model answers with rubbish - the repair prompt asks again."""
    answers = ["not json at all", '{"latex": "x = 2"}']
    prompts: list[str] = []

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            prompts.append(prompt)
            return answers.pop(0)

    service = Service(api_keys=["key"], mock=False)
    assert service.complete_json("the first prompt") == {"latex": "x = 2"}
    assert len(prompts) == 2
    assert "not json at all" in prompts[1]
