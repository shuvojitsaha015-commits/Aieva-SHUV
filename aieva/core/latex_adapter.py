"""LaTeX -> SymPy conversion.

Three backends are tried in order:

1. :func:`sympy.parsing.latex.parse_latex` (needs ``antlr4-python3-runtime==4.11.*``);
2. ``latex2sympy2`` when the optional extra is installed;
3. a small regex normaliser that rewrites the common LaTeX constructs into
   plain maths text, which is then fed to the safe parser.

If every backend fails a :class:`~aieva.core.errors.ParseError` is raised with a
message that says *why*.
"""

from __future__ import annotations

import re
from typing import Any

import sympy

from aieva.core.errors import ParseError
from aieva.core.safe_parse import parse_text_expression

#: LaTeX constructs the regex fallback cannot represent (regex syntax).
UNSUPPORTED_COMMANDS = (
    r"\\int",
    r"\\iint",
    r"\\oint",
    r"\\sum",
    r"\\prod",
    r"\\lim",
    r"\\begin",
    r"\\end",
)

#: Commands that no backend may turn into a plain expression.
_UNSUPPORTED_ALWAYS = (
    r"\\int",
    r"\\iint",
    r"\\oint",
    r"\\sum",
    r"\\prod",
    r"\\lim",
    r"\\begin",
)

#: Commands that are ambiguous in a plain expression - rejected by every backend.
_AMBIGUOUS_COMMANDS = (
    r"\\pm",
    r"\\mp",
    r"\\lesssim",
    r"\\geq",
    r"\\leq",
    r"\\neq",
)

#: Greek letters -> plain symbol names.
_GREEK = {
    "alpha": "alpha",
    "beta": "beta",
    "gamma": "gamma",
    "delta": "delta",
    "epsilon": "epsilon",
    "varepsilon": "epsilon",
    "zeta": "zeta",
    "eta": "eta",
    "theta": "theta",
    "vartheta": "theta",
    "iota": "iota",
    "kappa": "kappa",
    "lambda": "lambda",
    "mu": "mu",
    "nu": "nu",
    "xi": "xi",
    "omicron": "omicron",
    "rho": "rho",
    "sigma": "sigma",
    "tau": "tau",
    "upsilon": "upsilon",
    "phi": "phi",
    "varphi": "phi",
    "chi": "chi",
    "psi": "psi",
    "omega": "omega",
    "Gamma": "Gamma",
    "Delta": "Delta",
    "Theta": "Theta",
    "Lambda": "Lambda",
    "Xi": "Xi",
    "Pi": "Pi",
    "Sigma": "Sigma",
    "Phi": "Phi",
    "Psi": "Psi",
    "Omega": "Omega",
}

#: LaTeX function names -> the names the safe parser knows.
_FUNCTION_NAMES = {
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "cot": "cot",
    "sec": "sec",
    "csc": "csc",
    "arcsin": "asin",
    "arccos": "acos",
    "arctan": "atan",
    "sinh": "sinh",
    "cosh": "cosh",
    "tanh": "tanh",
    "exp": "exp",
    "log": "log",
    "ln": "ln",
    "lg": "log",
    "min": "min",
    "max": "max",
}

_CONSTANTS = {
    "pi": "pi",
    "infty": "oo",
    "infty ": "oo",
    "partial": "partial",
}


def _read_brace_group(text: str, start: int) -> tuple[str, int]:
    """Read a ``{...}`` group starting at ``start``. Returns (content, next_index)."""
    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    raise ParseError("Unbalanced braces in LaTeX expression")


def _read_single_token(text: str, start: int) -> tuple[str, int]:
    r"""Read a single LaTeX token (``2``, ``x``, ``\pi`` ...) starting at ``start``."""
    i = start
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text):
        raise ParseError("Unexpected end of LaTeX expression")
    if text[i] == "\\":
        j = i + 1
        while j < len(text) and text[j].isalpha():
            j += 1
        if j == i + 1:  # a single character command such as \%
            j = i + 2
        return text[i:j], j
    if text[i] == "{":
        return _read_brace_group(text, i)
    j = i
    while j < len(text) and (text[j].isalnum() or text[j] == "."):
        j += 1
    if j == i:
        raise ParseError(f"Unexpected character {text[i]!r} in LaTeX expression")
    return text[i:j], j


def _replace_fractions(text: str) -> str:
    """``\\frac{a}{b}`` -> ``((a)/(b))`` (works recursively)."""
    pattern = re.compile(r"\\(?:d|t)?frac")
    out: list[str] = []
    index = 0
    while True:
        match = pattern.search(text, index)
        if match is None:
            out.append(text[index:])
            break
        out.append(text[index : match.start()])
        pos = match.end()
        numerator, pos = _read_single_token(text, pos)
        denominator, pos = _read_single_token(text, pos)
        out.append(f"(({numerator})/({denominator}))")
        index = pos
    return "".join(out)


def _replace_sqrt(text: str) -> str:
    """``\\sqrt{x}`` -> ``sqrt(x)`` and ``\\sqrt[n]{x}`` -> ``((x)**(1/(n)))``."""
    out: list[str] = []
    index = 0
    while True:
        match = re.compile(r"\\sqrt").search(text, index)
        if match is None:
            out.append(text[index:])
            break
        out.append(text[index : match.start()])
        pos = match.end()
        root = None
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos < len(text) and text[pos] == "[":
            close = text.find("]", pos)
            if close == -1:
                raise ParseError("Unbalanced '[' in LaTeX expression")
            root = text[pos + 1 : close]
            pos = close + 1
        argument, pos = _read_single_token(text, pos)
        if root is None:
            out.append(f"sqrt({argument})")
        else:
            out.append(f"(({argument})**(1/({root})))")
        index = pos
    return "".join(out)


def _replace_braced_scripts(text: str) -> str:
    text = re.sub(r"\^\s*\{([^{}]*)\}", r"**(\1)", text)
    text = re.sub(r"\^\s*([A-Za-z0-9]+)", r"**(\1)", text)
    text = re.sub(r"_\s*\{([^{}]*)\}", r"_\1", text)
    text = re.sub(r"_\s*([A-Za-z0-9]+)", r"_\1", text)
    return text


def _replace_text_commands(text: str) -> str:
    """``\\mathrm{...}`` / ``\\text{...}`` / ``\\operatorname{...}`` -> plain content."""
    for command in (
        "mathrm",
        "mathbf",
        "mathit",
        "mathsf",
        "mathtt",
        "text",
        "textrm",
        "operatorname",
        "mbox",
    ):
        pattern = re.compile(r"\\" + command + r"\s*\{([^{}]*)\}")
        text = pattern.sub(lambda m: m.group(1).replace(" ", ""), text)
    return text


def normalize_latex(latex: str) -> str:
    """Rewrite a LaTeX expression into plain maths text.

    Raises :class:`ParseError` for constructs that cannot be represented.
    """
    if latex is None or not latex.strip():
        raise ParseError("Empty LaTeX expression")

    text = latex.strip()
    for command in UNSUPPORTED_COMMANDS:
        if re.search(command, text):
            raise ParseError(f"LaTeX command {command!r} is not supported by the plain-text parser")

    # spacing / delimiters
    text = re.sub(r"\\(left|right|displaystyle|textstyle|scriptstyle|limits|nolimits)\b", "", text)
    text = re.sub(r"\\[,;!:]", " ", text)
    text = text.replace("\\%", "").replace("\\$", "").replace("\\#", "").replace("\\_", "_")
    text = text.replace("\\{", "(").replace("\\}", ")")
    text = text.replace("~", "*")
    text = text.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/")
    text = text.replace("\\pm", "+").replace("\\mp", "-")

    text = _replace_text_commands(text)
    text = _replace_fractions(text)
    text = _replace_sqrt(text)
    text = _replace_braced_scripts(text)

    # functions
    for latex_name, plain_name in _FUNCTION_NAMES.items():
        text = re.sub(r"\\" + latex_name + r"(?![A-Za-z])", plain_name, text)
    # constants and greek letters
    for latex_name, plain_name in _GREEK.items():
        text = re.sub(r"\\" + latex_name + r"(?![A-Za-z])", plain_name, text)
    text = re.sub(r"\\pi(?![A-Za-z])", "pi", text)
    text = re.sub(r"\\infty(?![A-Za-z])", "oo", text)
    text = re.sub(r"\\infty(?![A-Za-z])", "oo", text)

    if "\\" in text:
        leftovers = sorted(set(re.findall(r"\\[A-Za-z]+", text)))
        raise ParseError(f"Unsupported LaTeX command(s): {', '.join(leftovers)}")
    return text


def _normalize_symbols(expression: sympy.Basic) -> sympy.Basic:
    """Clean up symbol names produced by the LaTeX parser.

    ``parse_latex`` returns ``Symbol("x_{1}")`` for ``x_{1}`` and
    ``Symbol("pi")`` for ``\\pi`` - both are normalised here.
    """
    replacements: dict[sympy.Basic, sympy.Basic] = {}
    for symbol in expression.free_symbols:
        name = symbol.name
        cleaned = name.replace("{", "").replace("}", "")
        if cleaned != name:
            replacements[symbol] = sympy.Symbol(cleaned)
        elif name == "pi":
            replacements[symbol] = sympy.pi
        elif name == "infty":
            replacements[symbol] = sympy.oo
    if not replacements:
        return expression
    return expression.xreplace(replacements)


def _split_top_level_equals(text: str) -> tuple[str, str] | None:
    """Split on the first ``=`` that is not inside a ``{...}`` group."""
    depth = 0
    for index, char in enumerate(text):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "=" and depth == 0:
            return text[:index], text[index + 1 :]
    return None


def _try_parse_latex(latex: str) -> sympy.Basic | None:
    try:
        from sympy.parsing.latex import parse_latex  # type: ignore import-not-found
    except Exception:  # noqa: BLE001 - antlr runtime missing
        return None
    try:
        result = parse_latex(latex)
    except Exception:  # noqa: BLE001 - invalid LaTeX
        return None
    if isinstance(result, sympy.Basic):
        return _normalize_symbols(result)
    return None


def _try_latex2sympy(latex: str) -> sympy.Basic | None:
    try:
        from latex2sympy2 import latex2sympy  # type: ignore import-not-found
    except Exception:  # noqa: BLE001 - optional dependency
        return None
    try:
        result = latex2sympy(latex)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(result, sympy.Basic):
        return _normalize_symbols(result)
    return None


def latex_to_sympy(latex: str) -> sympy.Basic:
    """Convert a LaTeX expression into a SymPy object.

    Raises :class:`ParseError` when the expression cannot be converted.
    """
    if latex is None or not latex.strip():
        raise ParseError("Empty LaTeX expression")
    text = latex.strip()
    for command in _UNSUPPORTED_ALWAYS:
        if re.search(command, text):
            raise ParseError(
                f"LaTeX command {command!r} is not a plain expression - "
                "use the solver for integrals, sums and limits"
            )
    for command in _AMBIGUOUS_COMMANDS:
        if re.search(command, text):
            raise ParseError(f"LaTeX command {command!r} cannot be represented as an expression")
    if _split_top_level_equals(text) is not None:
        raise ParseError(
            "This looks like an equation; use latex_to_equation() for 'lhs = rhs' input"
        )

    errors: list[str] = []

    result = _try_parse_latex(text)
    if result is not None:
        return result
    errors.append("sympy.parsing.latex.parse_latex failed")

    result = _try_latex2sympy(text)
    if result is not None:
        return result
    errors.append("latex2sympy2 failed")

    try:
        plain = normalize_latex(text)
        return parse_text_expression(plain)
    except ParseError as exc:
        errors.append(f"regex normaliser failed ({exc.message})")
        raise ParseError(
            f"Could not convert LaTeX {text!r} to a SymPy expression: " + "; ".join(errors)
        ) from exc


def latex_to_equation(latex: str) -> sympy.Eq:
    """Convert a LaTeX equation (``lhs = rhs``) into a :class:`sympy.Equality`."""
    if latex is None:
        raise ParseError("Empty LaTeX equation")
    parts = _split_top_level_equals(latex)
    if parts is None:
        raise ParseError(f"No '=' found in {latex!r}")
    lhs_text, rhs_text = (part.strip() for part in parts)
    lhs = latex_to_sympy(lhs_text)
    rhs = latex_to_sympy(rhs_text)
    return sympy.Eq(lhs, rhs, evaluate=False)


def latex_to_sympy_list(latex: str) -> list[sympy.Basic]:
    """Split a LaTeX string on ``,`` and convert every part."""
    return [latex_to_sympy(part) for part in latex.split(",") if part.strip()]


def sympy_to_latex(expr: Any) -> str:
    """Pretty-print a SymPy object as LaTeX (never raises)."""
    try:
        return sympy.latex(expr)
    except Exception:  # noqa: BLE001
        return str(expr)


__all__ = [
    "UNSUPPORTED_COMMANDS",
    "latex_to_equation",
    "latex_to_sympy",
    "latex_to_sympy_list",
    "normalize_latex",
    "sympy_to_latex",
]
