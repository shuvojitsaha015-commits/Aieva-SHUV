"""Several Gemini keys at the same time."""

from __future__ import annotations

from aieva.config import settings_from_env
from aieva.core.errors import CloudError
from server.services.gemini import GeminiService


def test_the_keys_are_read_from_the_environment() -> None:
    settings = settings_from_env({"GEMINI_API_KEYS": "key-a, key-b"})
    assert settings.all_gemini_keys == ("key-a", "key-b")


def test_a_semicolon_separates_the_keys_too() -> None:
    settings = settings_from_env({"GEMINI_API_KEYS": "key-a; key-b"})
    assert settings.all_gemini_keys == ("key-a", "key-b")


def test_the_single_key_is_still_used() -> None:
    """The old way keeps working."""
    settings = settings_from_env({"GEMINI_API_KEY": "key-a"})
    assert settings.all_gemini_keys == ("key-a",)


def test_the_keys_are_not_repeated() -> None:
    settings = settings_from_env({"GEMINI_API_KEY": "key-a", "GEMINI_API_KEYS": "key-a,key-b"})
    assert settings.all_gemini_keys == ("key-a", "key-b")


def test_without_a_key_there_is_nothing() -> None:
    settings = settings_from_env({})
    assert settings.all_gemini_keys == ()


def test_the_service_knows_every_key() -> None:
    service = GeminiService(api_keys=["k1", "k2", "k3"], mock=False)
    assert service.key_count == 3
    assert service.available is True


def test_the_service_without_a_key_cannot_call() -> None:
    service = GeminiService(api_keys=[], mock=False)
    assert service.available is False


def test_a_failing_key_is_skipped_at_once() -> None:
    """The second key answers without waiting - that is the whole point."""
    calls: list[str] = []

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            calls.append(key)
            if key == "broken":
                raise RuntimeError("the quota of this key is gone")
            return '{"latex": "x = 2"}'

    service = Service(api_keys=["broken", "good"], mock=False)
    answer = service.complete_json("the prompt")
    assert answer == {"latex": "x = 2"}
    assert calls == ["broken", "good"], "the good key was used right away"


def test_every_key_is_tried_before_the_waiting() -> None:
    """With three keys all three are tried before the backoff begins."""
    calls: list[str] = []

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            calls.append(key)
            raise RuntimeError("no key works")

    service = Service(api_keys=["k1", "k2", "k3"], mock=False)
    try:
        service.complete_json("the prompt")
    except CloudError:
        pass
    else:  # pragma: no cover - the call has to fail
        raise AssertionError("the call should have failed")

    assert calls[:3] == ["k1", "k2", "k3"], "every key was tried"


def test_the_repair_also_uses_the_keys() -> None:
    """The second chance goes through the same pool."""
    calls: list[str] = []

    class Service(GeminiService):
        def _call_once(self, prompt, image_bytes, mime_type, key=""):
            calls.append(key)
            if key == "broken":
                raise RuntimeError("the quota of this key is gone")
            if "not valid json" in prompt.lower():
                return '{"latex": "x = 2"}'
            return "this is not json"

    service = Service(api_keys=["broken", "good"], mock=False)
    answer = service.complete_json("the prompt")
    assert answer == {"latex": "x = 2"}
    assert "broken" in calls
    assert "good" in calls
