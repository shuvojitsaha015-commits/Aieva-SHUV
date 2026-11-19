"""Safe parsing of user / LLM supplied mathematical text.

**Never** use :func:`eval` or :func:`exec` on raw user input.  The pipeline is:

1. a strict character allow-list (no quotes, brackets, semicolons, ``=`` ...);
2. a deny-list of dangerous Python words and of *any* attribute access;
3. :func:`sympy.parsing.sympy_parser.parse_expr` with a restricted
   ``global_dict`` (no ``__builtins__``) and a whitelisted ``local_dict``.

Unknown names (``m``, ``c``, ``r`` ...) become SymPy symbols - that is exactly
what the parameter sliders need.
"""

from __future__ import annotations

import re
from typing import Any

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from aieva.core.errors import ParseError

#: Maximum length of a single expression handed to the parser.
MAX_EXPRESSION_LENGTH = 500

#: The biggest exponent that is accepted (``x**999999999`` would kill the
#: process when SymPy computes the roots).
MAX_EXPONENT = 1000

#: Only these characters may appear in an expression.
_ALLOWED_CHARS = re.compile(r"^[0-9A-Za-z_+\-*/^().,\s]*$")

#: Python words that have no business in a maths expression.
_DANGEROUS_WORDS = frozenset(
    {
        "__import__",
        "import",
        "lambda",
        "open",
        "exec",
        "eval",
        "execfile",
        "compile",
        "globals",
        "locals",
        "getattr",
        "setattr",
        "delattr",
        "breakpoint",
        "input",
        "exit",
        "quit",
        "os",
        "sys",
        "subprocess",
        "builtins",
        "__builtins__",
        "system",
        "popen",
        "socket",
        "requests",
        "pickle",
        "marshal",
        "ctypes",
        "shutil",
        "tempfile",
        "pathlib",
    }
)

_DANGEROUS_RE = re.compile(r"(?i)\b(" + "|".join(sorted(_DANGEROUS_WORDS)) + r")\b")

#: Numbers are removed before the "no attribute access" check so that ``3.14``
#: is not mistaken for ``something.something``.
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")

#: ``name.attribute`` - never allowed.
_ATTRIBUTE_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\s*\.")


def _safe_namespace() -> dict[str, Any]:
    """The restricted global namespace used for :func:`parse_expr`."""
    return {
        "Symbol": sympy.Symbol,
        "Function": sympy.Function,
        "AppliedUndef": sympy.core.function.AppliedUndef,
        "Integer": sympy.Integer,
        "Float": sympy.Float,
        "Rational": sympy.Rational,
        "Add": sympy.Add,
        "Mul": sympy.Mul,
        "Pow": sympy.Pow,
        "Tuple": sympy.Tuple,
        "Eq": sympy.Eq,
        "True": True,
        "False": False,
        # No builtins at all: the generated code may only use the names above.
        "__builtins__": {},
    }


#: Names a user is allowed to write.
ALLOWED_NAMES: dict[str, Any] = {
    # trigonometry
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "cot": sympy.cot,
    "sec": sympy.sec,
    "csc": sympy.csc,
    "asin": sympy.asin,
    "acos": sympy.acos,
    "atan": sympy.atan,
    "atan2": sympy.atan2,
    "sinh": sympy.sinh,
    "cosh": sympy.cosh,
    "tanh": sympy.tanh,
    "arcsin": sympy.asin,
    "arccos": sympy.acos,
    "arctan": sympy.atan,
    # exponentials / logs
    "exp": sympy.exp,
    "log": sympy.log,
    "ln": sympy.log,
    "log10": sympy.log,
    "sqrt": sympy.sqrt,
    "cbrt": sympy.cbrt,
    "Abs": sympy.Abs,
    "abs": sympy.Abs,
    "sign": sympy.sign,
    "floor": sympy.floor,
    "ceiling": sympy.ceiling,
    "Min": sympy.Min,
    "Max": sympy.Max,
    "min": sympy.Min,
    "max": sympy.Max,
    "re": sympy.re,
    "im": sympy.im,
    "factorial": sympy.factorial,
    "gamma": sympy.gamma,
    # constants
    "pi": sympy.pi,
    "e": sympy.E,
    "E": sympy.E,
    "I": sympy.I,
    "oo": sympy.oo,
    "inf": sympy.oo,
    "nan": sympy.nan,
}

#: Transformations used for every parse.
TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

_FUNCTION_DEFINITION_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z_0-9]*)\s*\(\s*(?P<arg>[A-Za-z_][A-Za-z_0-9]*)\s*\)\s*$"
)


def validate_expression(text: str) -> str:
    """Validate the *shape* of an expression. Raises :class:`ParseError`."""
    if text is None:
        raise ParseError("Empty expression")
    cleaned = text.strip()
    if not cleaned:
        raise ParseError("Empty expression")
    if len(cleaned) > MAX_EXPRESSION_LENGTH:
        raise ParseError(
            f"Expression too long ({len(cleaned)} characters, "
            f"maximum is {MAX_EXPRESSION_LENGTH})"
        )
    if "__" in cleaned:
        raise ParseError("Dunder names are not allowed")
    if not _ALLOWED_CHARS.match(cleaned):
        bad = sorted({c for c in cleaned if not _ALLOWED_CHARS.match(c)})
        raise ParseError(f"Illegal character(s) in expression: {''.join(bad)!r}")
    match = _DANGEROUS_RE.search(cleaned)
    if match:
        raise ParseError(f"Forbidden token in expression: {match.group(1)!r}")
    without_numbers = _NUMBER_RE.sub(" ", cleaned)
    if _ATTRIBUTE_RE.search(without_numbers):
        raise ParseError("Attribute access is not allowed in expressions")
    return cleaned


def check_exponents(expression: sympy.Basic) -> sympy.Basic:
    """Refuse an exponent that would blow the memory up.

    ``x**999999999`` is a short text, but SymPy would try to compute a
    billion roots - the process would die before the timeout of the solver
    could help. The exponent is therefore checked right after the parsing.
    """
    for node in expression.atoms(sympy.Pow):
        exponent = node.exp
        value: float | None = None
        if exponent.is_Integer:
            value = float(abs(int(exponent)))
        elif exponent.is_number:
            try:
                value = abs(float(exponent))
            except (TypeError, ValueError, OverflowError):
                value = None
        if value is not None and value > MAX_EXPONENT:
            raise ParseError(f"The exponent {value:g} is too large (the maximum is {MAX_EXPONENT})")
    return expression


def parse_text_expression(text: str) -> sympy.Basic:
    """Parse a plain-text maths expression into a SymPy object.

    Supports ``^`` as power, implicit multiplication (``2x``), ``3(x+1)`` and
    ``sin x``.
    """
    cleaned = validate_expression(text)
    local_dict = dict(ALLOWED_NAMES)
    try:
        expr = parse_expr(
            cleaned,
            local_dict=local_dict,
            global_dict=_safe_namespace(),
            transformations=TRANSFORMATIONS,
        )
    except ParseError:
        raise
    except Exception as exc:  # noqa: BLE001 - any parser failure is a ParseError
        raise ParseError(f"Could not parse {text!r}: {exc}") from exc
    if not isinstance(expr, sympy.Basic):
        raise ParseError(f"Parsed value is not a SymPy expression: {text!r}")
    return check_exponents(expr)


def parse_equation(text: str) -> sympy.Eq:
    """Parse ``lhs = rhs`` into a :class:`sympy.Equality`.

    Handles ``y = ...``, ``f(x) = ...`` and implicit curves such as
    ``x^2 + y^2 = 25``.
    """
    if text is None or "=" not in text:
        raise ParseError(f"No '=' found in {text!r}")
    raw = text.strip()
    if raw.count("=") > 1:
        raise ParseError("Only a single '=' is supported")
    lhs_text, rhs_text = (part.strip() for part in raw.split("=", 1))
    if not lhs_text or not rhs_text:
        raise ParseError("Both sides of the equation must be filled in")

    definition = _FUNCTION_DEFINITION_RE.match(lhs_text)
    if definition and definition.group("name") not in ALLOWED_NAMES:
        # a new function is defined: f(x) = x^2
        fname = definition.group("name")
        arg = definition.group("arg")
        lhs: sympy.Basic = sympy.Function(fname)(sympy.Symbol(arg))
    else:
        # a known function (sin, cos, log, ...) is a normal expression
        lhs = parse_text_expression(lhs_text)
    rhs = parse_text_expression(rhs_text)

    try:
        equation = sympy.Eq(lhs, rhs, evaluate=False)
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"Could not build an equation from {text!r}: {exc}") from exc
    check_exponents(equation)
    return equation


def split_equation(text: str) -> tuple[str, str]:
    """Return the two sides of an equation as plain strings."""
    if "=" not in text:
        raise ParseError(f"No '=' found in {text!r}")
    lhs, rhs = text.split("=", 1)
    return lhs.strip(), rhs.strip()


__all__ = [
    "MAX_EXPONENT",
    "ALLOWED_NAMES",
    "MAX_EXPRESSION_LENGTH",
    "TRANSFORMATIONS",
    "parse_equation",
    "parse_text_expression",
    "split_equation",
    "validate_expression",
]
