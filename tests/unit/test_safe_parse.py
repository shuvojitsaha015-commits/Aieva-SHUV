"""Phase 2: the safe parser must never execute user supplied code."""

from __future__ import annotations

import pytest
import sympy

from aieva.core.errors import ParseError
from aieva.core.safe_parse import (
    MAX_EXPRESSION_LENGTH,
    parse_equation,
    parse_text_expression,
    split_equation,
    validate_expression,
)

#: 30 hostile strings - none of them may ever be evaluated.
MALICIOUS = [
    "__import__('os').system('x')",
    "__import__('os').system('rm -rf /')",
    "os.system('ls')",
    "os.popen('id').read()",
    "subprocess.call(['ls'])",
    "open('/etc/passwd').read()",
    "exec('x=1')",
    "eval('1+1')",
    "compile('x', 'f', 'eval')",
    "globals()['__builtins__']",
    "locals()",
    "getattr(__import__('os'), 'system')('ls')",
    "setattr(__import__('os'), 'x', 1)",
    "delattr(__import__('os'), 'path')",
    "lambda x: x",
    "__import__('sys').exit()",
    "print('hello')",
    "input()",
    "breakpoint()",
    "exit()",
    "quit()",
    "().__class__.__bases__[0].__subclasses__()",
    "[].__class__.__mro__",
    "x.__class__",
    "import os",
    "from os import system",
    "raise SystemExit(1)",
    "assert False",
    "yield 1",
    "await x",
]


@pytest.mark.parametrize("payload", MALICIOUS)
def test_malicious_strings_are_rejected(payload: str) -> None:
    with pytest.raises(ParseError):
        parse_text_expression(payload)


@pytest.mark.parametrize("payload", MALICIOUS)
def test_malicious_strings_are_rejected_in_equations(payload: str) -> None:
    with pytest.raises(ParseError):
        parse_equation(f"x = {payload}")


def test_thirty_malicious_strings_are_covered() -> None:
    assert len(MALICIOUS) >= 30


def test_simple_expressions() -> None:
    assert parse_text_expression("x + 1") == sympy.Symbol("x") + 1
    assert parse_text_expression("2x + 3") == 2 * sympy.Symbol("x") + 3
    assert parse_text_expression("x^2") == sympy.Symbol("x") ** 2
    assert parse_text_expression("3(x+1)") == 3 * (sympy.Symbol("x") + 1)
    assert parse_text_expression("sin x") == sympy.sin(sympy.Symbol("x"))
    assert parse_text_expression("2 * sin(x)") == 2 * sympy.sin(sympy.Symbol("x"))


def test_whitelisted_names() -> None:
    x = sympy.Symbol("x")
    assert parse_text_expression("sqrt(x)") == sympy.sqrt(x)
    assert parse_text_expression("log(x)") == sympy.log(x)
    assert parse_text_expression("ln(x)") == sympy.log(x)
    assert parse_text_expression("exp(x)") == sympy.exp(x)
    assert parse_text_expression("Abs(x)") == sympy.Abs(x)
    assert parse_text_expression("pi").free_symbols == set()
    assert float(parse_text_expression("pi").evalf()) == pytest.approx(3.14159, rel=1e-4)


def test_unknown_names_become_symbols() -> None:
    expr = parse_text_expression("m*x + c")
    assert expr.free_symbols == {sympy.Symbol("m"), sympy.Symbol("x"), sympy.Symbol("c")}


def test_length_limit() -> None:
    with pytest.raises(ParseError):
        parse_text_expression("x" * (MAX_EXPRESSION_LENGTH + 1))


def test_empty_expression() -> None:
    with pytest.raises(ParseError):
        parse_text_expression("   ")


def test_parse_equation_shapes() -> None:
    eq = parse_equation("y = m*x + c")
    assert isinstance(eq, sympy.Equality)
    assert eq.lhs == sympy.Symbol("y")

    circle = parse_equation("x^2 + y^2 = 25")
    assert circle.lhs == sympy.Symbol("x") ** 2 + sympy.Symbol("y") ** 2
    assert circle.rhs == 25

    fn = parse_equation("f(x) = x^2")
    assert fn.lhs.func.__name__ == "f"


def test_parse_equation_errors() -> None:
    with pytest.raises(ParseError):
        parse_equation("y m*x")
    with pytest.raises(ParseError):
        parse_equation("y = ")
    with pytest.raises(ParseError):
        parse_equation("a = b = c")


def test_split_equation() -> None:
    assert split_equation("y = x + 1") == ("y", "x + 1")


def test_validate_expression_reports_bad_characters() -> None:
    with pytest.raises(ParseError) as excinfo:
        validate_expression("x; y")
    assert "Illegal character" in excinfo.value.message
