"""Phase 2: the LaTeX adapter must understand a wide range of maths LaTeX."""

from __future__ import annotations

import pytest
import sympy

from aieva.core.errors import ParseError
from aieva.core.latex_adapter import (
    latex_to_equation,
    latex_to_sympy,
    latex_to_sympy_list,
    normalize_latex,
    sympy_to_latex,
)

x = sympy.Symbol("x")
y = sympy.Symbol("y")
m = sympy.Symbol("m")
c = sympy.Symbol("c")
r = sympy.Symbol("r")

#: 25+ LaTeX expressions with their expected symbolic value.
EXPRESSIONS: list[tuple[str, object]] = [
    (r"x", x),
    (r"x^{2}", x**2),
    (r"x^{3} + 1", x**3 + 1),
    (r"2x", 2 * x),
    (r"2x + 3y", 2 * x + 3 * y),
    (r"m x + c", m * x + c),
    (r"\frac{1}{2}", sympy.Rational(1, 2)),
    (r"\frac{x}{2}", x / 2),
    (r"\frac{x + 1}{x - 1}", (x + 1) / (x - 1)),
    (r"\sin(x)", sympy.sin(x)),
    (r"\cos(x)", sympy.cos(x)),
    (r"\tan(x)", sympy.tan(x)),
    (r"\sqrt{x}", sympy.sqrt(x)),
    (r"\sqrt{x^{2} + 1}", sympy.sqrt(x**2 + 1)),
    (r"e^{x}", sympy.Symbol("e") ** x),
    (r"\log(x)", sympy.log(x)),
    (r"\ln(x)", sympy.log(x)),
    (r"\pi", sympy.pi),
    (r"2\pi r", 2 * sympy.pi * r),
    (r"|x|", sympy.Abs(x)),
    (r"x_{1}", sympy.Symbol("x_1")),
    (r"a \cdot b", sympy.Symbol("a") * sympy.Symbol("b")),
    (r"\frac{1}{x} + \frac{1}{y}", 1 / x + 1 / y),
    (r"3(x + 1)", 3 * (x + 1)),
    (r"-x^{2} + 4", -(x**2) + 4),
    (r"\theta", sympy.Symbol("theta")),
    (r"x / y", x / y),
]

#: Constructs the plain-text backend cannot represent.
UNSUPPORTED = [
    r"\int_0^1 x^{2} dx",
    r"\sum_{i=1}^{n} i",
    r"\begin{pmatrix} 1 & 2 \end{pmatrix}",
]


@pytest.mark.parametrize("latex,expected", EXPRESSIONS)
def test_latex_expressions(latex: str, expected: object) -> None:
    result = latex_to_sympy(latex)
    assert sympy.simplify(result - expected) == 0


def test_at_least_twenty_five_expressions() -> None:
    assert len(EXPRESSIONS) >= 25


@pytest.mark.parametrize("latex", UNSUPPORTED)
def test_unsupported_constructs_raise(latex: str) -> None:
    with pytest.raises(ParseError):
        latex_to_sympy(latex)


def test_equations() -> None:
    eq = latex_to_equation(r"x^{2} + y^{2} = r^{2}")
    assert isinstance(eq, sympy.Equality)
    assert eq.lhs == x**2 + y**2
    assert eq.rhs == r**2


def test_equation_without_equals() -> None:
    with pytest.raises(ParseError):
        latex_to_equation(r"x^{2}")


def test_expression_with_equals_is_rejected() -> None:
    with pytest.raises(ParseError):
        latex_to_sympy(r"y = mx + c")


def test_normalizer_produces_plain_text() -> None:
    plain = normalize_latex(r"\frac{1}{2}")
    assert "/" in plain
    assert "frac" not in plain


def test_latex_to_sympy_list() -> None:
    parts = latex_to_sympy_list("x, y, x^{2}")
    assert len(parts) == 3
    assert parts[2] == x**2


def test_sympy_to_latex() -> None:
    assert "x" in sympy_to_latex(x**2)


def test_empty_input() -> None:
    with pytest.raises(ParseError):
        latex_to_sympy("")


def test_regex_normaliser_is_used_when_the_parsers_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """The third backend must be able to handle the common constructs."""
    import aieva.core.latex_adapter as adapter

    monkeypatch.setattr(adapter, "_try_parse_latex", lambda _latex: None)
    monkeypatch.setattr(adapter, "_try_latex2sympy", lambda _latex: None)

    assert adapter.latex_to_sympy(r"\frac{1}{2}") == sympy.Rational(1, 2)
    assert adapter.latex_to_sympy(r"x^{2}") == x**2
    assert adapter.latex_to_sympy(r"2x + 1") == 2 * x + 1
    assert adapter.latex_to_sympy(r"\sqrt{x}") == sympy.sqrt(x)
    assert adapter.latex_to_sympy(r"\sin(x)") == sympy.sin(x)
    assert adapter.latex_to_sympy(r"x_{1}") == sympy.Symbol("x_1")


def test_normaliser_rejects_integrals(monkeypatch: pytest.MonkeyPatch) -> None:
    import aieva.core.latex_adapter as adapter

    monkeypatch.setattr(adapter, "_try_parse_latex", lambda _latex: None)
    monkeypatch.setattr(adapter, "_try_latex2sympy", lambda _latex: None)
    with pytest.raises(ParseError):
        adapter.latex_to_sympy(r"\int_0^1 x^{2} dx")
