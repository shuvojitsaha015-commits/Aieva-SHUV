"""Tests for on-screen calculus OCR parsing and solving."""

import sympy
from aieva.plugins.math.classify import classify
from aieva.plugins.math.solver import solve_expression
from aieva.core.safe_parse import parse_text_expression


def test_calculus_classification() -> None:
    assert classify(r"\int x^2 dx").problem_type == "integral"
    assert classify("Integral(x**2, x)").problem_type == "integral"
    assert classify("integrate(x**2, x)").problem_type == "integral"
    assert classify(r"\int_{0}^{2} x^2 dx").problem_type == "definite_integral"
    assert classify("Integral(x**2, (x, 0, 2))").problem_type == "definite_integral"
    assert classify(r"\frac{d}{dx} x^3").problem_type == "derivative"
    assert classify("diff(x**3, x)").problem_type == "derivative"
    assert classify(r"\lim_{x \to 0} \frac{\sin(x)}{x}").problem_type == "limit"
    assert classify("limit(sin(x)/x, x, 0)").problem_type == "limit"
    assert classify("Limit(sin(x)/x, x, 0)").problem_type == "limit"


def test_calculus_solving() -> None:
    # Indefinite Integral
    res1 = solve_expression("Integral(x**2, x)")
    assert res1.result.answer_text == "x**3/3"

    res2 = solve_expression(r"\int x^2 dx")
    assert res2.result.answer_text == "x**3/3"

    # Definite Integral
    res3 = solve_expression(r"\int_{0}^{2} x^2 dx")
    assert res3.result.answer_text == "8/3"

    res4 = solve_expression("Integral(x**2, (x, 0, 2))")
    assert res4.result.answer_text == "8/3"

    # Derivative
    res5 = solve_expression(r"\frac{d}{dx} x^3")
    assert res5.result.answer_text == "3*x**2"

    res6 = solve_expression("diff(x**3, x)")
    assert res6.result.answer_text == "3*x**2"

    # Limit
    res7 = solve_expression(r"\lim_{x \to 0} \frac{\sin(x)}{x}")
    assert res7.result.answer_text == "1"

    res8 = solve_expression("limit(sin(x)/x, x, 0)")
    assert res8.result.answer_text == "1"

    res9 = solve_expression("Limit(sin(x)/x, x, 0)")
    assert res9.result.answer_text == "1"
