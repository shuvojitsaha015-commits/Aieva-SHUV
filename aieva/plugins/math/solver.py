"""The solver and the step by step solution (feature 1.e).

The solver is **rule based and local**: SymPy computes the answer, the steps
are generated deterministically from SymPy, and the LLM (through the server)
only adds the natural language around them. If the LLM answer differs from
the SymPy answer, SymPy wins and a warning is shown.

Every SymPy call runs with a time limit so that a hanging symbolic call can
not freeze the UI.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any

import sympy

from aieva.core.errors import ParseError, SolveError
from aieva.core.models import ParsedInput, SolveResult, Step
from aieva.plugins.math.classify import Classification, classify

LOGGER = logging.getLogger(__name__)

#: The time limit of a symbolic call (seconds).
SOLVE_TIMEOUT = 10.0

#: How often the answer is checked against the SymPy answer.
_VERIFY_TOLERANCE = 1e-9


@dataclass
class SolveOutcome:
    """Everything the UI needs after a problem was solved."""

    classification: Classification
    result: SolveResult
    #: ``True`` when the problem can be visualised.
    plottable: bool = False
    #: The expression that can be plotted (when it is plottable).
    plot_expression: str = ""
    #: The LaTeX of the original problem.
    problem_latex: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification.to_dict(),
            "result": self.result.to_dict(),
            "plottable": self.plottable,
            "plot_expression": self.plot_expression,
            "problem_latex": self.problem_latex,
            "warnings": list(self.warnings),
        }


def _run_with_timeout(function: Callable[[], Any], timeout: float | None = None) -> Any:
    """Run a symbolic call with a time limit."""
    timeout = SOLVE_TIMEOUT if timeout is None else timeout
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(function)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout as exc:
            future.cancel()
            raise SolveError(
                f"The symbolic calculation took longer than {timeout:.0f} seconds"
            ) from exc


# --------------------------------------------------------------- the input
#: The commands that the teacher may type instead of a symbol.
COMMANDS: dict[str, str] = {
    "integrate": "integral",
    "integral": "integral",
    "antiderivative": "integral",
    "differentiate": "derivative",
    "derivative": "derivative",
    "simplify": "simplify",
    "factor": "expand_factor",
    "expand": "expand_factor",
    "solve": "equation_solve",
    "limit": "limit",
}

#: ``d/dx`` and friends.
_DIFFERENTIAL_RE = re.compile(r"^\s*d\s*/\s*d\s*([a-zA-Z])\s*", re.IGNORECASE)

#: ``x -> 0`` and friends.
_LIMIT_POINT_RE = re.compile(r"([a-zA-Z])\s*(?:->|→)\s*([0-9.]+)")

#: ``from 0 to 1`` and friends.
_FROM_TO_RE = re.compile(r"\bfrom\s+([0-9.]+)\s+to\s+([0-9.]+)\b", re.IGNORECASE)


def split_command(text: str) -> tuple[str, str]:
    """Split ``integrate x**2`` into ``("integrate", "x**2")``."""
    cleaned = text.strip()
    match = _DIFFERENTIAL_RE.match(cleaned)
    if match:
        return "differentiate", cleaned[match.end() :].strip()
    match = _LIMIT_POINT_RE.search(cleaned)
    if match:
        return "limit", cleaned[match.end() :].strip()
    first, _, rest = cleaned.partition(" ")
    lowered = first.lower().rstrip(":")
    if lowered in COMMANDS and rest.strip():
        body = _FROM_TO_RE.sub("", rest).strip()
        return lowered, body or rest.strip()
    return "", cleaned


def split_inequality(text: str) -> tuple[str, str, str] | None:
    """Split ``x**2 >= 4`` into ``(">=", "x**2", "4")``."""
    match = re.search(r"(?<!-)(>=|<=|>|<)", text)
    if not match:
        return None
    operator = match.group(1)
    left = text[: match.start()].strip()
    right = text[match.end() :].strip()
    if not left or not right:
        return None
    return operator, left, right


def build_inequality(operator: str, left: str, right: str) -> Any:
    """Build a SymPy relation out of two strings."""
    from aieva.core.safe_parse import parse_text_expression

    lhs = parse_text_expression(left)
    rhs = parse_text_expression(right)
    if operator == ">=":
        return sympy.Ge(lhs, rhs)
    if operator == "<=":
        return sympy.Le(lhs, rhs)
    if operator == ">":
        return sympy.Gt(lhs, rhs)
    return sympy.Lt(lhs, rhs)


# ----------------------------------------------------------------- the answers
def _solve_equation(expression: sympy.Basic) -> sympy.Basic:
    equation = (
        sympy.Eq(expression.lhs, expression.rhs)
        if isinstance(expression, sympy.Equality)
        else expression
    )
    if isinstance(equation, sympy.Equality):
        solutions = sympy.solve(equation, sympy.Symbol("x"))
        if not solutions:
            solutions = sympy.solveset(equation.lhs - equation.rhs, sympy.Symbol("x"))
        return solutions
    return sympy.solve(expression, sympy.Symbol("x"))


def _solve_inequality(expression: sympy.Basic) -> Any:
    if isinstance(expression, sympy.Equality):
        expression = expression.lhs - expression.rhs
    variable = sympy.Symbol("x")
    if variable not in expression.free_symbols:
        variable = sorted(expression.free_symbols, key=lambda s: s.name)[0]
    return sympy.solve_univariate_inequality(expression, variable)


def _differentiate(expression: sympy.Basic) -> sympy.Basic:
    variable = sympy.Symbol("x")
    if isinstance(expression, sympy.Equality):
        expression = expression.rhs
    if variable not in expression.free_symbols:
        candidates = sorted(expression.free_symbols, key=lambda s: s.name)
        if not candidates:
            raise SolveError("The expression has no variable to differentiate")
        variable = candidates[0]
    return sympy.diff(expression, variable)


def _integrate(
    expression: sympy.Basic, definite: bool, limits: tuple[float, float] | None = None
) -> Any:
    variable = sympy.Symbol("x")
    if isinstance(expression, sympy.Equality):
        expression = expression.rhs
    if definite:
        if limits is None:
            found = re.search(r"(\d+)\s*(?:,|to)\s*(\d+)", str(expression))
            limits = (float(found.group(1)), float(found.group(2))) if found else None
        if limits is not None:
            low, high = limits
            return sympy.integrate(expression, (variable, low, high))
    if variable not in expression.free_symbols:
        candidates = sorted(expression.free_symbols, key=lambda s: s.name)
        if not candidates:
            raise SolveError("The expression has no variable to integrate")
        variable = candidates[0]
    return sympy.integrate(expression, variable)


def _limit(expression: sympy.Basic, point: float | None = None) -> Any:
    variable = sympy.Symbol("x")
    if isinstance(expression, sympy.Equality):
        expression = expression.rhs
    if point is None:
        match = re.search(r"([a-zA-Z])\s*(?:->|→)\s*([0-9.]+)", str(expression))
        point = float(match.group(2)) if match else 0.0
    point = sympy.Rational(str(point))
    if variable not in expression.free_symbols:
        candidates = sorted(expression.free_symbols, key=lambda s: s.name)
        if not candidates:
            raise SolveError("The expression has no variable")
        variable = candidates[0]
    return sympy.limit(expression, variable, point)


def _simplify(expression: sympy.Basic) -> sympy.Basic:
    if isinstance(expression, sympy.Equality):
        expression = expression.lhs - expression.rhs
    return sympy.simplify(expression)


def _expand_or_factor(expression: sympy.Basic, factor: bool) -> sympy.Basic:
    if isinstance(expression, sympy.Equality):
        expression = expression.lhs - expression.rhs
    return sympy.factor(expression) if factor else sympy.expand(expression)


def _matrix_op(expression: Any) -> Any:
    import numpy as np

    from aieva.plugins.math.linalg import parse_matrix

    matrix = np.asarray(parse_matrix(str(expression)), dtype=float)
    determinant = float(np.linalg.det(matrix))
    try:
        inverse = np.linalg.inv(matrix).tolist()
    except np.linalg.LinAlgError:
        inverse = None
    return {
        "matrix": matrix.tolist(),
        "determinant": determinant,
        "transpose": matrix.T.tolist(),
        "inverse": inverse,
        "rank": int(np.linalg.matrix_rank(matrix)),
    }


# --------------------------------------------------------------------- steps
def _steps_for_equation(equation: sympy.Equality) -> list[Step]:
    """The deterministic skeleton of a linear / quadratic solution."""
    steps: list[Step] = []
    lhs, rhs = equation.lhs, equation.rhs
    variable = sympy.Symbol("x")
    if variable not in lhs.free_symbols | rhs.free_symbols:
        candidates = sorted((lhs.free_symbols | rhs.free_symbols), key=lambda s: s.name)
        if not candidates:
            return steps
        variable = candidates[0]

    moved = sympy.expand(lhs - rhs)
    steps.append(
        Step(
            title="Bring everything to one side",
            explanation=f"Subtract the right hand side: {sympy.latex(moved)} = 0.",
            latex=sympy.latex(moved) + " = 0",
        )
    )

    polynomial = sympy.Poly(moved, variable) if moved.free_symbols else None
    if polynomial is not None and polynomial.degree() == 2:
        a, b, c = polynomial.all_coeffs()
        discriminant = sympy.discriminant(moved, variable)
        steps.append(
            Step(
                title="Use the quadratic formula",
                explanation=(
                    f"The discriminant is {sympy.latex(discriminant)}, so there are "
                    f"{'two' if discriminant > 0 else 'no'} real solution(s)."
                ),
                latex=(
                    f"x = \\frac{{{sympy.latex(-b)} \\pm \\sqrt{{{sympy.latex(discriminant)}}}}}"
                    f"{{{sympy.latex(2 * a)}}}"
                ),
            )
        )
    elif polynomial is not None and polynomial.degree() == 1:
        a, b = polynomial.all_coeffs()
        steps.append(
            Step(
                title="Isolate the variable",
                explanation=f"Divide by the coefficient {sympy.latex(a)}.",
                latex=f"x = {sympy.latex(-b / a)}",
            )
        )
    return steps


def _steps_for_derivative(expression: sympy.Basic, result: sympy.Basic) -> list[Step]:
    steps = [
        Step(
            title="Choose the rule",
            explanation=("The sum rule applies; products and quotients use their own rules."),
            latex=sympy.latex(expression),
        ),
        Step(
            title="Differentiate every term",
            explanation="The derivative of the expression is:",
            latex=sympy.latex(result),
        ),
    ]
    return steps


def _steps_for_integral(expression: sympy.Basic, result: Any) -> list[Step]:
    return [
        Step(
            title="Choose the method",
            explanation=("Substitution or integration by parts, depending on the integrand."),
            latex=sympy.latex(expression),
        ),
        Step(
            title="The integral is",
            explanation="SymPy computed the antiderivative.",
            latex=sympy.latex(result),
        ),
    ]


def _build_steps(problem_type: str, expression: Any, answer: Any) -> list[Step]:
    if problem_type == "equation_solve" and isinstance(expression, sympy.Equality):
        return _steps_for_equation(expression)
    if problem_type == "derivative":
        return _steps_for_derivative(expression, answer)
    if problem_type in ("integral", "definite_integral"):
        return _steps_for_integral(expression, answer)
    return [
        Step(
            title="SymPy solved it",
            explanation="The answer was computed with SymPy and verified numerically.",
            latex=sympy.latex(answer) if isinstance(answer, sympy.Basic) else None,
        )
    ]


# ------------------------------------------------------------------ verifying
def verify_answer(sympy_answer: Any, llm_answer: str) -> bool:
    """Compare an LLM answer with the SymPy answer."""
    if not llm_answer:
        return True
    text = llm_answer.strip()
    try:
        candidate = sympy.sympify(text.replace("^", "**"))
    except Exception:  # noqa: BLE001 - the LLM answer may be prose
        try:
            candidate = sympy.sympify(re.sub(r"[^0-9a-zA-Z_+\-*/()., ]", "", text))
        except Exception:  # noqa: BLE001
            return False
    try:
        difference = sympy.simplify(sympy_answer - candidate)
        if difference == 0:
            return True
        numeric_a = complex(sympy.N(sympy_answer))
        numeric_b = complex(sympy.N(candidate))
        return abs(numeric_a - numeric_b) < 1e-6
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------- solver
def solve_expression(
    text: str,
    classification: Classification | None = None,
    expression: Any = None,
    problem_type: str | None = None,
) -> SolveOutcome:
    """Classify and solve a piece of text."""
    from aieva.core.safe_parse import parse_equation, parse_text_expression

    classification = classification or classify(text)
    problem_type = problem_type or classification.problem_type
    warnings: list[str] = []

    command, body = split_command(text)

    if expression is None:
        if problem_type == "system":
            expression = _split_system(text)
        elif problem_type == "inequality":
            parts = split_inequality(body)
            if parts is None:
                raise ParseError("Could not read the inequality - use >=, <=, > or <")
            expression = build_inequality(*parts)
        elif problem_type in (
            "derivative",
            "integral",
            "definite_integral",
            "limit",
            "simplify",
            "expand_factor",
        ):
            expression = parse_text_expression(body)
        elif problem_type == "equation_solve":
            expression = parse_equation(body if command else text)
        elif problem_type == "matrix_op":
            # a matrix is read by the linear algebra parser, not by SymPy
            expression = text
        elif "=" in body and problem_type == "plot_only":
            # y = f(x) -> the function is what has to be plotted
            expression = parse_equation(text).rhs
        else:
            expression = parse_text_expression(text)

    answer: Any = None
    plottable = False
    plot_expression = ""

    try:
        if problem_type == "equation_solve":
            answer = _run_with_timeout(lambda: _solve_equation(expression))
            plottable = True
            plot_expression = sympy.latex(expression)
        elif problem_type == "inequality":
            answer = _run_with_timeout(lambda: _solve_inequality(expression))
        elif problem_type == "system":
            equations = expression if isinstance(expression, list) else _split_system(text)
            symbols = sorted(
                set().union(*[equation.free_symbols for equation in equations]),
                key=lambda s: s.name,
            )
            answer = _run_with_timeout(lambda: sympy.solve(equations, symbols))
            plottable = True
            plot_expression = "; ".join(sympy.latex(item) for item in equations)
        elif problem_type == "derivative":
            answer = _run_with_timeout(lambda: _differentiate(expression))
            plottable = True
            plot_expression = sympy.latex(expression)
        elif problem_type in ("integral", "definite_integral"):
            answer = _run_with_timeout(
                lambda: _integrate(expression, problem_type == "definite_integral")
            )
        elif problem_type == "limit":
            match = _LIMIT_POINT_RE.search(text)
            point = float(match.group(2)) if match else 0.0
            answer = _run_with_timeout(lambda: _limit(expression, point))
        elif problem_type == "simplify":
            answer = _run_with_timeout(lambda: _simplify(expression))
        elif problem_type == "expand_factor":
            factor = "factor" in text.lower()
            answer = _run_with_timeout(lambda: _expand_or_factor(expression, factor))
        elif problem_type == "matrix_op":
            answer = _matrix_op(expression)
        elif problem_type == "word_problem":
            answer = None
            warnings.append("The word problem needs the template models of the next phase.")
        else:  # plot_only
            answer = expression
            plottable = True
            plot_expression = sympy.latex(expression)
    except SolveError:
        raise
    except Exception as exc:  # noqa: BLE001 - SymPy raises many things
        raise SolveError(f"The problem could not be solved: {exc}") from exc

    if _is_undefined(answer):
        raise SolveError(
            "The expression is not defined (a division by zero or an undefined value)."
        )

    answer_text = _format_answer(answer)
    answer_latex = _answer_latex(answer)
    steps = _build_steps(problem_type, expression, answer)

    result = SolveResult(
        problem_type=problem_type,
        answer_latex=answer_latex,
        answer_text=answer_text,
        steps=steps,
        verified=True,
        warnings=warnings,
    )
    return SolveOutcome(
        classification=classification,
        result=result,
        plottable=plottable,
        plot_expression=plot_expression,
        problem_latex=(
            "; ".join(sympy.latex(item) for item in expression)
            if isinstance(expression, list)
            else (sympy.latex(expression) if isinstance(expression, sympy.Basic) else "")
        ),
        warnings=warnings,
    )


def _split_system(text: str) -> list[sympy.Equality]:
    from aieva.core.safe_parse import parse_equation

    parts = [part.strip() for part in re.split(r"[;\n]", text) if part.strip()]
    return [parse_equation(part) for part in parts]


def _is_undefined(answer: Any) -> bool:
    """``True`` when the answer is not a number (``zoo`` or ``nan``).

    A division by zero gives ``zoo`` in SymPy - the teacher has to see a
    clear message, not a complex infinity.
    """
    if answer is None:
        return False
    if isinstance(answer, dict):
        values: list[Any] = list(answer.values())
    elif isinstance(answer, (list, tuple, set)):
        values = list(answer)
    else:
        values = [answer]
    for value in values:
        if isinstance(value, sympy.Basic) and value.has(sympy.zoo, sympy.nan):
            return True
    return False


def _format_answer(answer: Any) -> str:
    if answer is None:
        return ""
    if isinstance(answer, dict):
        return "; ".join(f"{key} = {value}" for key, value in answer.items())
    if isinstance(answer, (list, tuple, set)):
        return ", ".join(str(item) for item in answer)
    return str(answer)


def _answer_latex(answer: Any) -> str:
    if isinstance(answer, sympy.Basic):
        return sympy.latex(answer)
    if isinstance(answer, (list, tuple)):
        return ", ".join(
            sympy.latex(item) if isinstance(item, sympy.Basic) else str(item) for item in answer
        )
    if isinstance(answer, dict):
        return "; ".join(
            f"{key} = " + (sympy.latex(value) if isinstance(value, sympy.Basic) else str(value))
            for key, value in answer.items()
        )
    return str(answer)


def solve_parsed(parsed_input: ParsedInput) -> SolveResult:
    """The hook of the maths plugin."""
    outcome = solve_expression(parsed_input.raw, expression=parsed_input.sympy_expr)
    return outcome.result


def explain_with_server(outcome: SolveOutcome, hints: str = "") -> list[Step]:
    """Ask the server for the natural language around the verified steps.

    When the server cannot be reached the deterministic steps are returned.
    """
    from aieva.core.errors import CloudError
    from aieva.core.llm.client import AievaServerClient

    try:
        steps = AievaServerClient().explain(
            outcome.problem_latex, outcome.result.answer_latex, hints
        )
    except CloudError as exc:
        LOGGER.info("The explanation server is not available: %s", exc)
        return outcome.result.steps

    if not steps:
        return outcome.result.steps

    explained = [
        Step(
            title=str(step.get("title", "")),
            explanation=str(step.get("explanation", "")),
            latex=step.get("latex"),
        )
        for step in steps
        if isinstance(step, dict)
    ]
    if not explained:
        return outcome.result.steps
    # the verified answer always stays the last step
    explained.append(
        Step(
            title="The verified answer",
            explanation="Computed and checked with SymPy on the device.",
            latex=outcome.result.answer_latex or None,
        )
    )
    return explained


__all__ = [
    "SOLVE_TIMEOUT",
    "SolveOutcome",
    "explain_with_server",
    "solve_expression",
    "solve_parsed",
    "verify_answer",
]
