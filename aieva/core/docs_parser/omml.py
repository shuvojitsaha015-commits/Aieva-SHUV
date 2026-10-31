"""A minimal converter from OMML (Office Math Markup) to LaTeX.

Word and PowerPoint store their equations as OMML inside the XML of the
document. The converter walks the tree and writes the LaTeX of the parts it
knows; everything it does not know is skipped (the text of the run is kept,
so nothing is lost).

The module never uses ``eval`` / ``exec`` - it only reads the XML.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The namespace of the Office Math Markup.
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

#: The characters that OMML uses for the operators.
OPERATOR_NAMES: dict[str, str] = {
    "∑": r"\sum",
    "∏": r"\prod",
    "∫": r"\int",
    "∬": r"\iint",
    "∭": r"\iiint",
    "∮": r"\oint",
    "√": r"\sqrt",
    "∞": r"\infty",
    "≤": r"\leq",
    "≥": r"\geq",
    "≠": r"\neq",
    "≈": r"\approx",
    "≡": r"\equiv",
    "×": r"\times",
    "÷": r"\div",
    "±": r"\pm",
    "∓": r"\mp",
    "→": r"\rightarrow",
    "←": r"\leftarrow",
    "⇒": r"\Rightarrow",
    "⇔": r"\Leftrightarrow",
    "∈": r"\in",
    "∉": r"\notin",
    "⊂": r"\subset",
    "⊆": r"\subseteq",
    "∪": r"\cup",
    "∩": r"\cap",
    "∅": r"\emptyset",
    "∀": r"\forall",
    "∃": r"\exists",
    "∂": r"\partial",
    "∇": r"\nabla",
    "°": r"^{\circ}",
    "…": r"\dots",
    "⋅": r"\cdot",
    "′": "'",
    "″": "''",
}

#: The accents of OMML (``m:acc``).
ACCENT_NAMES: dict[str, str] = {
    "̂": r"\hat",
    "̃": r"\tilde",
    "̄": r"\bar",
    "̆": r"\breve",
    "̇": r"\dot",
    "̈": r"\ddot",
    "⃗": r"\vec",
    "⃖": r"\overleftarrow",
}


def _tag(element: Any) -> str:
    """The local name of the tag of an element (``{ns}oMath`` -> ``oMath``)."""
    tag = getattr(element, "tag", "")
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _attr(element: Any, name: str) -> str:
    """The value of an attribute (the math namespace is used as well)."""
    if element is None:
        return ""
    value = element.get(name)
    if value:
        return str(value)
    value = element.get(f"{{{MATH_NS}}}{name}")
    return str(value) if value else ""


def _children(element: Any, name: str) -> list[Any]:
    """The direct children with a given local name."""
    return [child for child in element if _tag(child) == name]


def _first(element: Any, name: str) -> Any | None:
    found = _children(element, name)
    return found[0] if found else None


def _text(element: Any) -> str:
    """The text of the runs below an element."""
    parts: list[str] = []
    for node in element.iter():
        if _tag(node) == "t" and node.text:
            parts.append(node.text)
    return "".join(parts)


def _escape(text: str) -> str:
    """Escape the characters that mean something in LaTeX."""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\^{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def _run_text(run: Any) -> str:
    """The LaTeX of a run (``m:r``) - the operators are translated."""
    raw = _text(run)
    if not raw:
        return ""
    parts: list[str] = []
    for char in raw:
        if char in OPERATOR_NAMES:
            parts.append(OPERATOR_NAMES[char])
        elif char == "^":
            parts.append("^")
        else:
            parts.append(char)
    return "".join(parts)


def _delimiter(element: Any) -> str:
    """``m:d`` - the brackets around an expression."""
    properties = _first(element, "dPr")
    begin = "("
    end = ")"
    if properties is not None:
        beg = _first(properties, "begChr")
        end_char = _first(properties, "endChr")
        if beg is not None and _attr(beg, "val"):
            begin = _attr(beg, "val")
        if end_char is not None and _attr(end_char, "val"):
            end = _attr(end_char, "val")
    inside = "".join(convert(child) for child in element if _tag(child) in ("e", "num"))
    return rf"\left{begin}{inside}\right{end}"


def _fraction(element: Any) -> str:
    """``m:f`` - a fraction."""
    numerator = _first(element, "num")
    denominator = _first(element, "den")
    top = convert(numerator) if numerator is not None else ""
    bottom = convert(denominator) if denominator is not None else ""
    return rf"\frac{{{top}}}{{{bottom}}}"


def _radical(element: Any) -> str:
    """``m:rad`` - a square root."""
    degree = _first(element, "deg")
    base = _first(element, "e")
    root = ""
    if degree is not None and _text(degree).strip():
        root = f"[{_text(degree).strip()}]"
    return rf"\sqrt{root}{{{convert(base) if base is not None else ''}}}"


def _subsup(element: Any, kind: str) -> str:
    """``m:sSub`` / ``m:sSup`` / ``m:sSubSup`` - the scripts."""
    base = _first(element, "e")
    sub = _first(element, "sub")
    sup = _first(element, "sup")
    body = convert(base) if base is not None else ""
    if kind == "sub":
        return rf"{body}_{{{convert(sub) if sub is not None else ''}}}"
    if kind == "sup":
        return rf"{body}^{{{convert(sup) if sup is not None else ''}}}"
    return (
        rf"{body}_{{{convert(sub) if sub is not None else ''}}}"
        rf"^{{{convert(sup) if sup is not None else ''}}}"
    )


def _nary(element: Any) -> str:
    """``m:nary`` - a sum, a product or an integral."""
    properties = _first(element, "naryPr")
    operator = "∑"
    if properties is not None:
        char = _first(properties, "chr")
        if char is not None and _attr(char, "val"):
            operator = _attr(char, "val")
    symbol = OPERATOR_NAMES.get(operator, r"\sum")
    sub = _first(element, "sub")
    sup = _first(element, "sup")
    body = _first(element, "e")
    lower = convert(sub) if sub is not None else ""
    upper = convert(sup) if sup is not None else ""
    if lower or upper:
        symbol = rf"{symbol}_{{{lower}}}^{{{upper}}}"
    inner = convert(body) if body is not None else ""
    return rf"{symbol} {inner}"


def _accent(element: Any) -> str:
    """``m:acc`` - an accent over a letter."""
    properties = _first(element, "accPr")
    name = r"\hat"
    if properties is not None:
        char = _first(properties, "chr")
        if char is not None and _attr(char, "val"):
            name = ACCENT_NAMES.get(_attr(char, "val"), r"\hat")
    base = _first(element, "e")
    return rf"{name}{{{convert(base) if base is not None else ''}}}"


def _function(element: Any) -> str:
    """``m:func`` - a function name with its argument."""
    name = _first(element, "fName")
    body = _first(element, "e")
    function_name = _text(name).strip() if name is not None else ""
    argument = convert(body) if body is not None else ""
    return rf"\operatorname{{{function_name}}}({argument})" if function_name else argument


def _matrix(element: Any) -> str:
    """``m:m`` - a matrix of equations."""
    rows: list[str] = []
    for row in _children(element, "mr"):
        cells = [convert(cell) for cell in _children(row, "e")]
        rows.append(" & ".join(cells))
    body = r" \\ ".join(rows)
    return rf"\begin{{matrix}} {body} \end{{matrix}}"


def _group(element: Any) -> str:
    """``m:e`` and everything else that only groups."""
    return "".join(convert(child) for child in element if _tag(child) != "e" or True)


def _join(parts: list[str]) -> str:
    """Join the parts of a formula - the operators get a space around them."""
    result = ""
    for part in parts:
        if not part:
            continue
        if (
            result
            and (result[-1] in "+-=<>,/ " or part[0] in "+-=<>,/")
            and not result.endswith(" ")
            and not part.startswith(" ")
        ):
            result += " "
        result += part
    return result


def convert(element: Any) -> str:
    """The LaTeX of one OMML element."""
    if element is None:
        return ""
    tag = _tag(element)
    if tag == "oMath" or tag == "oMathPara":
        return _join([convert(child) for child in element if _tag(child) != "oMathPara"])
    if tag == "r":
        return _run_text(element)
    if tag == "t":
        return _escape(element.text or "")
    if tag == "f":
        return _fraction(element)
    if tag == "rad":
        return _radical(element)
    if tag == "d":
        return _delimiter(element)
    if tag == "sSub":
        return _subsup(element, "sub")
    if tag == "sSup":
        return _subsup(element, "sup")
    if tag == "sSubSup":
        return _subsup(element, "subsup")
    if tag == "nary":
        return _nary(element)
    if tag == "acc":
        return _accent(element)
    if tag == "func":
        return _function(element)
    if tag == "m":
        return _matrix(element)
    if tag == "limLow":
        base = _first(element, "e")
        limit = _first(element, "lim")
        return rf"{convert(base)}_{{{convert(limit) if limit is not None else ''}}}"
    if tag == "limUpp":
        base = _first(element, "e")
        limit = _first(element, "lim")
        return rf"{convert(base)}^{{{convert(limit) if limit is not None else ''}}}"
    if tag in ("e", "num", "den", "deg", "sub", "sup", "fName"):
        return "".join(convert(child) for child in element)
    if tag in ("ctrlPr", "rPr", "dPr", "naryPr", "accPr", "funcPr", "mPr", "boxPr", "argPr"):
        return ""
    # everything else: the text is kept, the structure is ignored
    text = _text(element)
    return _escape(text) if text else ""


def omml_to_latex(element: Any) -> str:
    """The LaTeX of an ``m:oMath`` element (or of a list of them)."""
    if element is None:
        return ""
    if isinstance(element, (list, tuple)):
        return " ".join(omml_to_latex(item) for item in element)
    latex = convert(element).strip()
    return latex


__all__ = ["ACCENT_NAMES", "MATH_NS", "OPERATOR_NAMES", "convert", "omml_to_latex"]
