"""The request that the teacher taps on the board."""

import json

from aieva.core.service.scan import (
    clear_request,
    forget_region,
    read_region,
    read_request,
    remember_region,
    request_path,
    write_request,
)


def test_the_request_is_written(tmp_path) -> None:
    state = tmp_path / "service_state.json"
    target = write_request(state)
    assert target == request_path(state)
    assert target.is_file()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["region"] is None
    assert payload["at"] > 0


def test_the_area_of_the_board_is_kept(tmp_path) -> None:
    state = tmp_path / "service_state.json"
    write_request(state, region=(10, 20, 30, 40))
    payload = read_request(state)
    assert payload is not None
    assert payload["region"] == [10, 20, 30, 40]


def test_the_request_is_read_back(tmp_path) -> None:
    state = tmp_path / "service_state.json"
    write_request(state)
    payload = read_request(state)
    assert payload is not None
    assert "at" in payload


def test_without_a_request_there_is_nothing(tmp_path) -> None:
    assert read_request(tmp_path / "service_state.json") is None


def test_the_request_is_taken_away(tmp_path) -> None:
    state = tmp_path / "service_state.json"
    write_request(state)
    clear_request(state)
    assert read_request(state) is None


def test_the_area_of_the_board_is_remembered(tmp_path) -> None:
    state = tmp_path / "service_state.json"
    remember_region(state, (10, 20, 30, 40))
    assert read_region(state) == (10, 20, 30, 40)


def test_without_an_area_there_is_nothing(tmp_path) -> None:
    assert read_region(tmp_path / "service_state.json") is None


def test_the_area_can_be_forgotten(tmp_path) -> None:
    state = tmp_path / "service_state.json"
    remember_region(state, (1, 2, 3, 4))
    forget_region(state)
    assert read_region(state) is None


def test_the_whole_board_is_read_when_no_area_was_picked(tmp_path) -> None:
    state = tmp_path / "service_state.json"
    remember_region(state, None)
    assert read_region(state) is None
