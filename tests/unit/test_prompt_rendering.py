"""The prompts must survive the JSON braces.

The prompts of Aieva show the wanted JSON to the model, so they are full
of braces::

    {
      "problem_type": "kinematic_projectile"
    }

``str.format`` reads every ``{...}`` as a placeholder - and the server
died with::

    KeyError: '\\n  "problem_type"'

The renderer of :mod:`aieva.core.llm.prompts` fills the placeholders
without touching the JSON body. These tests keep that promise.
"""

from __future__ import annotations

import pytest

from aieva.core.llm.prompts import (
    EXPLAIN_PROMPT,
    OCR_PROMPT,
    REPAIR_PROMPT,
    WORDPROBLEM_PROMPT,
    render_prompt,
)


def test_the_prompts_really_contain_braces() -> None:
    """Without braces the test below would prove nothing."""
    assert "{" in WORDPROBLEM_PROMPT
    assert "{" in EXPLAIN_PROMPT
    assert "{" in OCR_PROMPT
    assert "{" in REPAIR_PROMPT


def test_render_prompt_fills_the_placeholder() -> None:
    result = render_prompt("Hello {name}!", name="teacher")
    assert result == "Hello teacher!"


def test_render_prompt_keeps_the_json_body() -> None:
    prompt = render_prompt(WORDPROBLEM_PROMPT, text="a ball")
    assert "a ball" in prompt
    assert '"problem_type"' in prompt
    assert "{" in prompt


def test_render_prompt_does_not_raise_on_the_json_braces() -> None:
    """The old ``str.format`` died with a KeyError here."""
    prompt = render_prompt(WORDPROBLEM_PROMPT, text="a ball")
    assert prompt.startswith("You turn a word problem")


@pytest.mark.parametrize(
    ("template", "values"),
    [
        (WORDPROBLEM_PROMPT, {"text": "a ball"}),
        (
            EXPLAIN_PROMPT,
            {"problem_latex": "x^2", "sympy_answer": "2", "hints": "none"},
        ),
        (REPAIR_PROMPT, {"broken": "not json"}),
    ],
)
def test_every_prompt_can_be_rendered(template: str, values: dict[str, str]) -> None:
    """No prompt of Aieva may break the server."""
    prompt = render_prompt(template, **values)
    assert prompt
    for value in values.values():
        assert value in prompt


def test_the_ocr_prompt_has_no_placeholder_and_stays_whole() -> None:
    """The OCR prompt is fixed - it must survive unchanged."""
    assert render_prompt(OCR_PROMPT) == OCR_PROMPT
    assert '"latex"' in render_prompt(OCR_PROMPT)


def test_render_prompt_replaces_every_occurrence() -> None:
    template = "{a} and {a} and {b}"
    assert render_prompt(template, a="1", b="2") == "1 and 1 and 2"


def test_render_prompt_without_a_placeholder_changes_nothing() -> None:
    assert render_prompt("plain text") == "plain text"


def test_render_prompt_ignores_unknown_placeholders() -> None:
    """A placeholder that is not filled stays as it is."""
    assert render_prompt("{known} {unknown}", known="yes") == "yes {unknown}"
