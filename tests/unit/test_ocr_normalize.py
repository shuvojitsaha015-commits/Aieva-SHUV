"""The clean-up of the text that was read from the board."""

from aieva.core.ocr.normalize import looks_like_math, normalize_math_text


def test_the_symbols_of_the_board_are_translated() -> None:
    assert normalize_math_text("x² + 2·x − 3") == "x**2 + 2*x - 3"
    assert normalize_math_text("√(x+1)") == "sqrt(x+1)"
    assert normalize_math_text("2 × π") == "2 * pi"
    assert normalize_math_text("6 ÷ 2") == "6 / 2"


def test_the_relations_are_translated() -> None:
    assert normalize_math_text("x ≤ 3") == "x <= 3"
    assert normalize_math_text("x ≥ 3") == "x >= 3"
    assert normalize_math_text("x ≠ 3") == "x != 3"


def test_the_text_is_cleaned_up() -> None:
    assert normalize_math_text("  x = 2.  ") == "x = 2"
    assert normalize_math_text("x = 2\ny = 3") == "x = 2 y = 3"
    assert normalize_math_text("") == ""
    assert normalize_math_text("   ") == ""


def test_the_points_are_not_cut_off() -> None:
    assert normalize_math_text("3.14") == "3.14"
    assert normalize_math_text("x = 2.5") == "x = 2.5"


def test_a_sentence_is_not_maths() -> None:
    assert looks_like_math("hello there") is False
    assert looks_like_math("") is False
    assert looks_like_math("x + 1") is True
    assert looks_like_math("sin(x)") is True
    assert looks_like_math("x") is True
    assert looks_like_math("42") is True
