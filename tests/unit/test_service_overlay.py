"""The floating window above the board."""

import json

from aieva.core.service.overlay import pretty, read_result, result_stamp


def test_a_missing_file_gives_nothing(tmp_path) -> None:
    assert read_result(tmp_path / "nope.json") is None


def test_a_broken_file_gives_nothing(tmp_path) -> None:
    path = tmp_path / "last_result.json"
    path.write_text("{oops", encoding="utf-8")
    assert read_result(path) is None


def test_a_file_that_is_not_an_object_gives_nothing(tmp_path) -> None:
    path = tmp_path / "last_result.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert read_result(path) is None


def test_the_result_is_read(tmp_path) -> None:
    path = tmp_path / "last_result.json"
    path.write_text(json.dumps({"plain": "x**2 = 4", "created_at": 12}), encoding="utf-8")
    payload = read_result(path)
    assert payload is not None
    assert payload["plain"] == "x**2 = 4"


def test_the_stamp_changes_with_the_result() -> None:
    first = result_stamp({"plain": "x", "created_at": 1})
    second = result_stamp({"plain": "y", "created_at": 1})
    assert first != second
    assert first == result_stamp({"plain": "x", "created_at": 1})


def test_the_reading_is_pretty() -> None:
    assert pretty("x**2 + 2*x") == "x² + 2·x"
    assert pretty("sqrt(2)") == "√(2)"
    assert pretty("") == ""
