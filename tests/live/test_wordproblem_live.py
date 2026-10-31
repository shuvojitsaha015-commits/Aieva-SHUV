"""The live test of Phase 9 (needs a real Gemini key).

The test is skipped when ``GEMINI_API_KEY`` is not set, so the normal test run
stays offline::

    GEMINI_API_KEY=... pytest -m live tests/live
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def _needs_a_key():
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY is not set - the live test is skipped")


def test_a_real_word_problem_becomes_a_model():
    """The LLM turns a word problem into the structured model."""
    from aieva.core.llm.prompts import WORDPROBLEM_PROMPT
    from server.services.gemini import GeminiService

    service = GeminiService()
    if not service.available:
        pytest.skip("the Gemini service is not available")

    text = "A ball is thrown with 20 m/s at 45 degrees. How high does it fly and how far?"
    answer = service.complete_json(WORDPROBLEM_PROMPT.format(text=text))

    assert isinstance(answer, dict)
    assert answer.get("problem_type") in {
        "kinematic_projectile",
        "uniform_motion",
        "optimization",
        "rate_tank",
        "geometry",
        "mixture",
        "unsupported",
    }
    assert isinstance(answer.get("variables"), list)


def test_a_real_model_can_be_solved_and_drawn():
    """The model of the LLM is understood by the templates."""
    from aieva.core.llm.prompts import WORDPROBLEM_PROMPT
    from aieva.plugins.math.wordproblems import (
        WordProblem,
        solve_word_problem,
        visualize_word_problem,
    )
    from server.services.gemini import GeminiService

    service = GeminiService()
    if not service.available:
        pytest.skip("the Gemini service is not available")

    text = "A ball is thrown with 20 m/s at 45 degrees. How high does it fly and how far?"
    answer = service.complete_json(WORDPROBLEM_PROMPT.format(text=text))
    problem = WordProblem.from_dict(answer)

    if not problem.supported:
        pytest.skip(f"the model was not supported: {problem.problem_type}")

    solution = solve_word_problem(problem)
    assert solution.values
    result = visualize_word_problem(problem, solution)
    assert result.figure is not None
