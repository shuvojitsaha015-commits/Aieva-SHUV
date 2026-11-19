"""The clean-up of a text that was read from the board.

The board hands us what a camera sees: ``x² + 2·x − 3``, ``x**2/2``,
``√(x+1)``. SymPy only understands a small, safe language - so the text is
translated into it first, and only then it is checked.

Nothing is guessed here: only the way the board writes a symbol is
normalised, so the maths itself never changes.
"""

from __future__ import annotations

import re

#: The symbols the board uses and SymPy does not.
_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("×", "*"),  # ×
    ("·", "*"),  # ·
    ("⋅", "*"),  # ⋅
    ("÷", "/"),  # ÷
    ("−", "-"),  # −
    ("–", "-"),  # –
    ("—", "-"),  # —
    ("²", "**2"),  # ²
    ("³", "**3"),  # ³
    ("⁴", "**4"),  # ⁴
    ("√", "sqrt"),  # √
    ("π", "pi"),  # π
    ("∫", "int"),  # ∫
    ("Σ", "sum"),  # Σ
    ("∏", "prod"),  # ∏
    ("∞", "oo"),  # ∞
    ("≤", "<="),  # ≤
    ("≥", ">="),  # ≥
    ("≠", "!="),  # ≠
    ("≈", "~"),  # ≈
    ("′", "'"),  # ′
    ("“", ""),  # “
    ("”", ""),  # ”
    ("‘", ""),  # ‘
    ("’", ""),  # ’
    ("\xa0", " "),  # the space that does not break
)

#: A text only counts as mathematics when it has a number, an operator or a
#: function in it - otherwise every word would be a product of letters.
_MEANINGFUL_RE = re.compile(
    r"[0-9]|[+\-*/^()]|\b(sin|cos|tan|cot|sec|csc|asin|acos|atan|sinh|cosh|tanh"
    r"|exp|log|ln|sqrt|abs|pi|e)\b"
)


def normalize_math_text(text: str) -> str:
    """Translate what the board shows into the language of SymPy."""
    result = (text or "").strip()
    if not result:
        return ""
    for old, new in _REPLACEMENTS:
        result = result.replace(old, new)
    result = result.replace("\n", " ")
    result = re.sub(r"\s+", " ", result).strip()
    # a point at the end is a full stop, not a multiplication
    if result.endswith(".") and not result.endswith(".."):
        result = result[:-1].strip()
    return result


def looks_like_math(text: str) -> bool:
    """``True`` when the text can be a formula (and not a sentence)."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    if re.fullmatch(r"[A-Za-z]", stripped):
        return True
    return bool(_MEANINGFUL_RE.search(stripped))


__all__ = ["looks_like_math", "normalize_math_text"]
