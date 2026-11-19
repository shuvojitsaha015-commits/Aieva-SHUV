"""What should be done with the problem that was read."""

from __future__ import annotations

from aieva.core.service.intent import Intent, decide, from_classification, from_text
from aieva.plugins.math.classify import classify


def test_gemini_can_ask_for_the_answer() -> None:
    intent = from_text("solve")
    assert intent is not None
    assert intent.solve is True
    assert intent.graph is False
    assert intent.source == "gemini"


def test_gemini_can_ask_for_the_graph() -> None:
    intent = from_text("graph")
    assert intent is not None
    assert intent.solve is False
    assert intent.graph is True


def test_gemini_can_ask_for_both() -> None:
    intent = from_text("both")
    assert intent is not None
    assert intent.solve is True
    assert intent.graph is True


def test_gemini_can_say_there_is_no_maths() -> None:
    intent = from_text("none")
    assert intent is not None
    assert intent.solve is False
    assert intent.graph is False


def test_the_intent_is_read_case_insensitively() -> None:
    intent = from_text("  SOLVE  ")
    assert intent is not None
    assert intent.solve is True


def test_a_nonsense_intent_is_ignored() -> None:
    assert from_text("maybe") is None
    assert from_text("") is None


def test_the_rules_are_the_fallback() -> None:
    classification = classify("y = x**2 + 3*x")
    intent = decide("", classification)
    assert intent.source == "rules"
    assert intent.graph is True


def test_a_function_is_only_plotted_by_the_rules() -> None:
    classification = classify("y = x**2 + 3*x")
    intent = from_classification(classification)
    assert intent.solve is False
    assert intent.graph is True


def test_an_equation_is_solved_and_plotted_by_the_rules() -> None:
    classification = classify("2*x + 3 = 7")
    intent = from_classification(classification)
    assert intent.solve is True
    assert intent.graph is True


def test_gemini_wins_over_the_rules() -> None:
    classification = classify("y = x**2 + 3*x")
    intent = decide("solve", classification)
    assert intent.source == "gemini"
    assert intent.solve is True
    assert intent.graph is False


def test_the_intent_can_be_written_down() -> None:
    intent = Intent(solve=True, graph=False, source="gemini", raw="solve")
    payload = intent.to_dict()
    assert payload["solve"] is True
    assert payload["graph"] is False
    assert payload["source"] == "gemini"
