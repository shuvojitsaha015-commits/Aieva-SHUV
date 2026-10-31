"""Phase 2: the core data models."""

from __future__ import annotations

from aieva.core.models import ParamSpec, ParsedInput, SolveResult, Step, VisualizationResult


def test_step_roundtrip() -> None:
    step = Step(title="Isolate x", explanation="subtract 3", latex="x = 5")
    assert Step.from_dict(step.to_dict()) == step


def test_parsed_input_roundtrip() -> None:
    parsed = ParsedInput(raw="y = x", kind="text", latex="y = x", source="manual", confidence=0.5)
    data = parsed.to_dict()
    assert data["kind"] == "text"
    assert data["confidence"] == 0.5


def test_solve_result_roundtrip() -> None:
    result = SolveResult(
        problem_type="equation_solve",
        answer_latex="x = 5",
        answer_text="x = 5",
        steps=[Step("One", "because")],
        verified=True,
        warnings=["careful"],
    )
    restored = SolveResult.from_dict(result.to_dict())
    assert restored.problem_type == "equation_solve"
    assert restored.steps[0].title == "One"
    assert restored.verified is True


def test_param_spec_roundtrip() -> None:
    spec = ParamSpec(name="m", default=1.0, min=-10.0, max=10.0, step=0.1)
    assert ParamSpec.from_dict(spec.to_dict()) == spec


def test_visualization_result_defaults() -> None:
    result = VisualizationResult()
    assert result.figure is None
    assert result.image_bytes is None
    assert result.parameters == []
    assert result.meta == {}
