"""The status file of the background service."""

import json

from aieva.core.service.state import ServiceState


def test_the_state_is_saved_and_read(tmp_path) -> None:
    state = ServiceState(status="running", pid=42, runs=3, last_plain="x**2 = 4")
    path = state.save(tmp_path / "state.json")
    assert path.is_file()
    loaded = ServiceState.load(path)
    assert loaded.status == "running"
    assert loaded.pid == 42
    assert loaded.runs == 3
    assert loaded.last_plain == "x**2 = 4"


def test_a_missing_file_gives_the_default(tmp_path) -> None:
    assert ServiceState.load(tmp_path / "nope.json").status == "stopped"


def test_a_broken_file_gives_the_default(tmp_path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    assert ServiceState.load(path).status == "stopped"


def test_the_write_leaves_no_temporary_file(tmp_path) -> None:
    state = ServiceState()
    path = state.save(tmp_path / "state.json")
    assert not (tmp_path / "state.json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "stopped"


def test_the_unknown_fields_land_in_extra(tmp_path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"status": "running", "surprise": 1}), encoding="utf-8")
    state = ServiceState.load(path)
    assert state.status == "running"
    assert state.extra == {"surprise": 1}


def test_the_uptime_is_counted() -> None:
    state = ServiceState(started_at=100.0)
    assert state.uptime_seconds(now=160.0) == 60.0
    assert state.uptime_seconds(now=50.0) == 0.0
    assert ServiceState().uptime_seconds(now=10.0) == 0.0
