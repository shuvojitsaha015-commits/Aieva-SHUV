"""The word problem templates (Phase 9).

The tests solve the 15 curated problems of ``tests/fixtures/golden_json``
and check the number and the picture of every one of them.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt  # noqa: E402

from aieva.core.errors import ParseError, SolveError  # noqa: E402
from aieva.plugins.math.templates import CATEGORIES, TEMPLATES, get_template  # noqa: E402
from aieva.plugins.math.wordproblems import (  # noqa: E402
    KNOWN_BUT_UNSUPPORTED,
    SUPPORTED_TYPES,
    WordProblem,
    solve_word_problem,
    visualize_word_problem,
)

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "golden_json"

#: The expected answer of every curated problem.
EXPECTED: dict[str, dict[str, float]] = {
    "projectile_20ms_45deg": {"max_height": 10.2041, "range": 40.8163, "flight_time": 2.8855},
    "projectile_30ms_30deg": {"max_height": 11.4796, "range": 79.5324, "flight_time": 3.0612},
    "projectile_25ms_60deg": {"max_height": 23.9158, "range": 55.2299, "flight_time": 4.4184},
    "car_catches_bus": {"meeting_time": 40.0, "meeting_point": 600.0},
    "walker_meets_train": {"meeting_time": 28.3019, "meeting_point": 339.6226},
    "cyclists_meet": {"meeting_time": 25.0, "meeting_point": 300.0},
    "farmer_fence": {"x": 20.0, "objective": 400.0},
    "rectangle_perimeter": {"x": 7.5, "objective": 56.25},
    "profit_maximum": {"x": 10.0, "objective": 50.0},
    "tank_net_rate": {"time": 60.0, "net_rate": 10.0},
    "two_taps": {"time": 4.0, "net_rate": 25.0},
    "tank_drains": {"time": 41.6667, "net_rate": -12.0},
    "rectangle_5x8": {"area": 40.0, "perimeter": 26.0},
    "circle_radius_3": {"area": 28.2743, "perimeter": 18.8496},
    "right_triangle_3_4": {"area": 6.0, "perimeter": 12.0},
}


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


def _load(name: str) -> WordProblem:
    data = json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8"))
    return WordProblem.from_dict(data)


def _golden_names() -> list[str]:
    return sorted(path.stem for path in GOLDEN.glob("*.json"))


# --------------------------------------------------------------------- the model
def test_from_dict_reads_the_model():
    problem = _load("car_catches_bus")
    assert problem.problem_type == "uniform_motion"
    assert problem.supported
    assert len(problem.variables) == 4
    assert problem.number("v1") == 15
    assert problem.unit("v1") == "m/s"
    assert problem.value("missing", 7.0) == 7.0


def test_from_dict_survives_a_hostile_model():
    """The answer of the LLM is untrusted input."""
    problem = WordProblem.from_dict(
        {
            "problem_type": "geometry",
            "variables": [
                {"name": "w", "value": "not a number"},
                {"name": "", "value": 3},
                "not an object",
                {"name": "h", "value": 8, "unit": "m"},
            ],
            "equations": [42, "", "A = w*h"],
            "unknowns": ["area", None],
            "parameters_for_sliders": ["w"],
            "assumptions": ["g = 9.8 m/s^2"],
        }
    )
    assert [variable.name for variable in problem.variables] == ["w", "h"]
    assert problem.value("w", 1.0) == 1.0  # the bad value is dropped
    assert problem.equations == ["42", "A = w*h"]
    assert problem.unknowns == ["area"]
    assert problem.symbols()["g"] == pytest.approx(9.8)


def test_from_dict_rejects_a_model_that_is_not_an_object():
    with pytest.raises(ParseError):
        WordProblem.from_dict(["not", "an", "object"])  # type: ignore[arg-type]


def test_number_of_a_missing_variable_is_an_error():
    problem = _load("circle_radius_3")
    with pytest.raises(SolveError):
        problem.number("w")
    with pytest.raises(SolveError):
        problem.number("nothing")


def test_confirmation_card():
    card = _load("farmer_fence").confirmation_card()
    assert card["problem_type"] == "optimization"
    assert card["supported"] is True
    assert card["variables"][0]["name"] == "L"
    assert "A = x*(L - x)" in card["equations"]


def test_slider_specs():
    specs = _load("projectile_20ms_45deg").slider_specs()
    assert [spec.name for spec in specs] == ["v0", "theta"]
    assert specs[0].default == 20
    assert specs[0].min < 20 < specs[0].max


# ------------------------------------------------------------------ the templates
def test_the_four_categories_exist():
    assert CATEGORIES == ("kinematic", "optimization", "rate", "geometry")
    assert set(TEMPLATES) == set(SUPPORTED_TYPES)
    for problem_type in SUPPORTED_TYPES:
        template = get_template(problem_type)
        assert callable(template.solve)
        assert callable(template.render)


def test_an_unknown_template_is_an_error():
    with pytest.raises(SolveError):
        get_template("chemistry")


def test_a_known_but_unsupported_type_is_an_error():
    problem = WordProblem.from_dict({"problem_type": "mixture"})
    assert problem.problem_type in KNOWN_BUT_UNSUPPORTED
    assert not problem.supported
    with pytest.raises(SolveError):
        solve_word_problem(problem)


# ----------------------------------------------------------------- the 15 problems
@pytest.mark.parametrize("name", _golden_names())
def test_every_curated_problem_has_the_right_answer(name):
    problem = _load(name)
    solution = solve_word_problem(problem)
    expected = EXPECTED[name]
    for key, value in expected.items():
        assert key in solution.values, f"{name}: {key} is missing"
        assert solution.values[key] == pytest.approx(value, rel=1e-3, abs=1e-3)
    assert solution.steps, f"{name}: there are no steps"
    assert solution.answer_text


@pytest.mark.parametrize("name", _golden_names())
def test_every_curated_problem_draws_a_figure(name):
    problem = _load(name)
    solution = solve_word_problem(problem)
    result = visualize_word_problem(problem, solution)
    assert result.figure is not None
    assert result.meta["kind"] == "word_problem"
    assert result.meta["template"] == problem.problem_type
    axes = result.figure.get_axes()
    assert axes, f"{name}: the figure has no axes"
    # the figure can really be written out (a PNG with a sensible size)
    path = GOLDEN.parent / f"_tmp_{name}.png"
    result.figure.savefig(path, dpi=60)
    assert path.stat().st_size > 3000
    path.unlink()


def test_there_are_at_least_twelve_curated_problems():
    assert len(_golden_names()) >= 12


# ------------------------------------------------------------------ the failures
def test_a_projectile_with_a_bad_angle():
    data = json.loads((GOLDEN / "projectile_20ms_45deg.json").read_text())
    data["variables"][1]["value"] = 120
    with pytest.raises(SolveError):
        solve_word_problem(WordProblem.from_dict(data))


def test_a_tank_without_a_net_rate():
    data = json.loads((GOLDEN / "tank_net_rate.json").read_text())
    data["variables"][1]["value"] = 30
    with pytest.raises(SolveError):
        solve_word_problem(WordProblem.from_dict(data))


def test_two_objects_with_the_same_speed():
    data = json.loads((GOLDEN / "car_catches_bus.json").read_text())
    data["variables"][1]["value"] = 15
    with pytest.raises(SolveError):
        solve_word_problem(WordProblem.from_dict(data))


def test_an_empty_tank_needs_no_time():
    data = json.loads((GOLDEN / "tank_drains.json").read_text())
    data["variables"][3]["value"] = 0
    solution = solve_word_problem(WordProblem.from_dict(data))
    assert solution.values["time"] == pytest.approx(0.0)


def test_a_tank_that_is_already_too_full():
    data = json.loads((GOLDEN / "tank_net_rate.json").read_text())
    data["variables"][3]["value"] = 700  # more than the capacity of 600
    with pytest.raises(SolveError):
        solve_word_problem(WordProblem.from_dict(data))


def test_an_optimization_without_an_objective():
    data = json.loads((GOLDEN / "farmer_fence.json").read_text())
    data["equations"] = ["A = 5"]
    with pytest.raises(SolveError):
        solve_word_problem(WordProblem.from_dict(data))


def test_a_negative_value_gives_a_warning():
    data = json.loads((GOLDEN / "two_taps.json").read_text())
    data["variables"][0]["value"] = -25
    solution = solve_word_problem(WordProblem.from_dict(data))
    assert any("negative" in warning for warning in solution.warnings)


def test_a_missing_unit_gives_a_warning():
    data = json.loads((GOLDEN / "two_taps.json").read_text())
    data["variables"][0]["unit"] = ""
    solution = solve_word_problem(WordProblem.from_dict(data))
    assert any("unit" in warning for warning in solution.warnings)


# ------------------------------------------------------------------- the physics
def test_the_projectile_formula_matches_the_numbers():
    problem = _load("projectile_30ms_30deg")
    solution = solve_word_problem(problem)
    speed = 30.0
    angle = math.radians(30)
    gravity = 9.8
    assert solution.values["max_height"] == pytest.approx(
        (speed * math.sin(angle)) ** 2 / (2 * gravity), rel=1e-6
    )
    assert solution.values["range"] == pytest.approx(
        speed**2 * math.sin(2 * angle) / gravity, rel=1e-6
    )


def test_the_uniform_motion_formula_matches_the_numbers():
    problem = _load("cyclists_meet")
    solution = solve_word_problem(problem)
    assert solution.values["meeting_time"] == pytest.approx(100 / 4, rel=1e-6)
    assert solution.values["meeting_point"] == pytest.approx(100 + 8 * 25, rel=1e-6)


def test_the_animation_points_follow_the_trajectory():
    from aieva.plugins.math.templates import kinematic

    problem = _load("projectile_20ms_45deg")
    solution = solve_word_problem(problem)
    points = kinematic.animation_points(problem, solution)
    assert len(points["times"]) == 120
    assert points["y"][0] == pytest.approx(0.0)
    assert points["y"].max() == pytest.approx(solution.values["max_height"], rel=1e-2)
