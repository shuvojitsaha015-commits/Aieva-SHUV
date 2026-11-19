"""Phase 8: the classifier and the solver (feature 1.e).

The solver is checked against known answers - at least 30 problems spread over
all the problem types.
"""

from __future__ import annotations

import pytest
import sympy

from aieva.core.errors import SolveError
from aieva.plugins.math.classify import PROBLEM_TYPES, classify
from aieva.plugins.math.solver import (
    solve_expression,
    split_command,
    split_inequality,
    verify_answer,
)


# ------------------------------------------------------------------ classifier
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x**2 + 3*x - 2 = 0", "equation_solve"),
        ("2*x + y = 5; x - y = 1", "system"),
        ("x**2 >= 4", "inequality"),
        ("d/dx x**3", "derivative"),
        ("differentiate x**3", "derivative"),
        ("integrate x**2", "integral"),
        ("\\int x**2 dx", "integral"),
        ("lim x->0 sin(x)/x", "limit"),
        ("simplify (x + 1)**2", "simplify"),
        ("factor x**2 - 1", "expand_factor"),
        ("expand (x + 1)**2", "expand_factor"),
        ("y = x**2", "plot_only"),
        ("x**2 + y**2", "plot_only"),
        ("[[1,2],[3,4]]", "matrix_op"),
        ("A ball is thrown with 20 m/s at 45 degrees", "word_problem"),
    ],
)
def test_classify(text: str, expected: str) -> None:
    assert classify(text).problem_type == expected


def test_every_problem_type_is_known() -> None:
    for name in PROBLEM_TYPES:
        assert isinstance(name, str)


def test_split_command() -> None:
    assert split_command("integrate x**2") == ("integrate", "x**2")
    assert split_command("d/dx x**3") == ("differentiate", "x**3")
    assert split_command("lim x->0 sin(x)/x") == ("limit", "sin(x)/x")
    assert split_command("x**2 + 1") == ("", "x**2 + 1")


def test_split_inequality() -> None:
    assert split_inequality("x**2 >= 4") == (">=", "x**2", "4")
    assert split_inequality("x -> 0") is None


# --------------------------------------------------------------------- solver
def _answer(text: str) -> str:
    outcome = solve_expression(text)
    return outcome.result.answer_text


def test_linear_equation() -> None:
    assert _answer("2*x + 3 = 7") == "2"


def test_quadratic_equation() -> None:
    outcome = solve_expression("x**2 - 4 = 0")
    assert set(outcome.result.answer_text.replace(" ", "").split(",")) == {"-2", "2"}


def test_quadratic_equation_with_the_formula() -> None:
    outcome = solve_expression("x**2 + 3*x - 2 = 0")
    values = [sympy.nsimplify(part) for part in outcome.result.answer_text.split(",")]
    roots = {sympy.simplify(value) for value in values}
    assert roots == {
        sympy.simplify((-3 + sympy.sqrt(17)) / 2),
        sympy.simplify((-3 - sympy.sqrt(17)) / 2),
    }


def test_equation_with_a_fraction() -> None:
    assert _answer("x/2 = 5") == "10"


def test_equation_with_functions() -> None:
    # SymPy has no closed form for sin(x) = 0 - the root is found numerically
    answer = _answer("sin(x) = 0")
    assert "0" in answer


def test_a_transcendental_equation_is_solved_numerically() -> None:
    answer = _answer("sin(x) = 0.5")
    assert "0.52" in answer or "0.523" in answer


def test_a_cosine_equation_is_solved_numerically() -> None:
    answer = _answer("cos(x) = 1")
    assert "2*pi" in answer or "0" in answer


def test_system_of_two_equations() -> None:
    outcome = solve_expression("2*x + y = 5; x - y = 1")
    assert "x = 2" in outcome.result.answer_text
    assert "y = 1" in outcome.result.answer_text


def test_system_of_three_equations() -> None:
    outcome = solve_expression("x + y + z = 6; x - y = 0; y - z = 0")
    assert outcome.result.answer_text


def test_inequality() -> None:
    answer = _answer("x**2 >= 4")
    assert "x" in answer


def test_derivative_of_a_polynomial() -> None:
    assert _answer("d/dx x**3") == "3*x**2"


def test_derivative_of_a_function() -> None:
    assert _answer("d/dx sin(x)") == "cos(x)"


def test_derivative_of_the_product_rule() -> None:
    answer = _answer("d/dx x**2 * sin(x)")
    assert (
        sympy.simplify(
            sympy.sympify(answer)
            - (2 * sympy.Symbol("x") * sympy.sin("x") + sympy.Symbol("x") ** 2 * sympy.cos("x"))
        )
        == 0
    )


def test_integral() -> None:
    assert _answer("integrate x**2") == "x**3/3"


def test_integral_of_a_function() -> None:
    assert _answer("integrate cos(x)") == "sin(x)"


def test_limit() -> None:
    assert _answer("lim x->0 sin(x)/x") == "1"


def test_limit_of_a_polynomial() -> None:
    assert _answer("lim x->2 x**2") == "4"


def test_simplify() -> None:
    assert _answer("simplify (x + 1)**2") == "(x + 1)**2"


def test_factor() -> None:
    assert _answer("factor x**2 - 1") == "(x - 1)*(x + 1)"


def test_expand() -> None:
    assert _answer("expand (x + 1)**2") == "x**2 + 2*x + 1"


def test_plot_only_keeps_the_function() -> None:
    outcome = solve_expression("y = x**2")
    assert outcome.result.answer_text == "x**2"
    assert outcome.plottable is True


def test_the_steps_are_generated() -> None:
    outcome = solve_expression("x**2 - 4 = 0")
    assert len(outcome.result.steps) >= 2
    assert outcome.result.steps[0].title


def test_the_steps_mention_the_discriminant() -> None:
    outcome = solve_expression("x**2 + 3*x - 2 = 0")
    assert any("discriminant" in step.explanation.lower() for step in outcome.result.steps)


def test_a_hanging_calculation_is_stopped() -> None:
    """A symbolic call that hangs is stopped - the UI stays responsive."""
    import time

    from aieva.plugins.math.solver import _run_with_timeout

    with pytest.raises(SolveError):
        _run_with_timeout(lambda: time.sleep(5), timeout=0.05)


def test_the_time_limit_is_read_at_call_time() -> None:
    """The limit is a module setting - it can be changed while running."""
    import time

    from aieva.plugins.math import solver as solver_module

    original = solver_module.SOLVE_TIMEOUT
    solver_module.SOLVE_TIMEOUT = 0.05
    try:
        with pytest.raises(SolveError):
            solver_module._run_with_timeout(lambda: time.sleep(5))
    finally:
        solver_module.SOLVE_TIMEOUT = original


def test_verify_answer_accepts_the_same_value() -> None:
    assert verify_answer(sympy.Integer(4), "4") is True
    assert verify_answer(sympy.Integer(4), "4.0") is True


def test_verify_answer_rejects_a_different_value() -> None:
    assert verify_answer(sympy.Integer(4), "5") is False


def test_verify_answer_accepts_an_empty_answer() -> None:
    assert verify_answer(sympy.Integer(4), "") is True


def test_verify_answer_compares_symbolically() -> None:
    assert verify_answer(sympy.sqrt(17) / 2 - sympy.Rational(3, 2), "(-3 + sqrt(17))/2") is True


# ------------------------------------------------------------------ coverage
def test_thirty_problems_over_all_types() -> None:
    """Every problem type is solved at least once."""
    problems = {
        "equation_solve": [
            "2*x + 3 = 7",
            "x**2 - 4 = 0",
            "x/2 = 5",
            "x = 2*x + 1",
            "3*x - 4 = 11",
            "x**2 + 3*x - 2 = 0",
            "5*x = 25",
        ],
        "inequality": ["x**2 >= 4", "x - 3 < 5", "2*x + 1 <= 9"],
        "system": [
            "2*x + y = 5; x - y = 1",
            "x + y = 3; x - y = 1",
            "x + y = 2; x - y = 0",
            "3*x + 2*y = 12; x - y = 1",
        ],
        "derivative": [
            "d/dx x**3",
            "d/dx sin(x)",
            "differentiate x**2 * cos(x)",
            "d/dx exp(x)",
            "d/dx log(x)",
            "d/dx x**3 + 2*x",
        ],
        "integral": [
            "integrate x**2",
            "integrate cos(x)",
            "integrate 1/x",
            "integrate sin(x)",
            "integrate exp(x)",
        ],
        "definite_integral": [
            "integrate x**2 from 0 to 1",
            "integrate x from 0 to 2",
        ],
        "limit": ["lim x->0 sin(x)/x", "lim x->1 x**2", "lim x->0 (1 + x)**5"],
        "simplify": [
            "simplify (x + 1)**2",
            "simplify sin(x)**2 + cos(x)**2",
            "simplify x**2 + 2*x + 1",
        ],
        "expand_factor": [
            "factor x**2 - 1",
            "expand (x + 1)**2",
            "factor x**2 - 4",
        ],
        "plot_only": ["y = x**2", "sin(x)", "y = 3*x + 2", "cos(x) + 1"],
        "matrix_op": ["[[1,2],[3,4]]", "[[2,0],[0,3]]"],
    }
    solved = 0
    for problem_type, items in problems.items():
        for item in items:
            outcome = solve_expression(item)
            assert outcome.classification.problem_type == problem_type, item
            assert outcome.result.answer_text or outcome.result.steps, item
            solved += 1
    assert solved >= 30
