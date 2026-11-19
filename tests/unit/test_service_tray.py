"""The tests of the icon in the system tray."""

from __future__ import annotations

import json
from pathlib import Path

from aieva.core.service.tray import (
    MENU_OPEN,
    MENU_QUIT,
    MENU_SCAN,
    MENU_START,
    MENU_STOP,
    dispatch,
    make_icon,
    menu_commands,
    open_frontend,
    scan_board,
    stop_service,
    tray_available,
)


def test_the_menu_has_the_four_entries() -> None:
    labels = [command.label for command in menu_commands()]
    assert MENU_OPEN in labels
    assert MENU_SCAN in labels
    assert MENU_QUIT in labels


def test_the_stop_entry_changes_when_the_service_runs() -> None:
    running = [command.label for command in menu_commands(service_running=True)]
    stopped = [command.label for command in menu_commands(service_running=False)]
    assert MENU_STOP in running
    assert MENU_START in stopped


def test_the_icon_is_drawn() -> None:
    image = make_icon(64)
    assert image.size == (64, 64)
    # the icon is not empty - there is a blue square with a white letter
    colors = set(image.getdata())
    assert len(colors) > 2


def test_the_menu_can_be_built_without_pystray() -> None:
    """The module has to work on a machine without a system tray."""
    assert isinstance(tray_available(), bool)


def test_opening_the_frontend_starts_the_application(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_popen(command: list[str], **kwargs: object) -> object:
        calls.append(command)
        return object()

    import aieva.core.service.tray as tray_module

    original = tray_module.subprocess.Popen
    tray_module.subprocess.Popen = fake_popen  # type: ignore[assignment]
    try:
        message = open_frontend("/usr/bin/python3")
    finally:
        tray_module.subprocess.Popen = original  # type: ignore[assignment]

    assert "starting" in message.lower()
    assert calls, "the application was not started"
    assert calls[0][1:] == ["-m", "aieva.ui.app"]


def test_scanning_the_board_writes_the_request(tmp_path: Path) -> None:
    state_file = tmp_path / "service_state.json"
    message = scan_board(state_file)
    assert "read" in message.lower()
    request = tmp_path / "scan_request"
    assert request.is_file()
    payload = json.loads(request.read_text(encoding="utf-8"))
    assert "at" in payload


def test_stopping_the_service_writes_the_stop_request(tmp_path: Path) -> None:
    state_file = tmp_path / "service_state.json"
    message = stop_service(state_file)
    assert "stop" in message.lower()
    assert (tmp_path / "stop_request").is_file()


def test_the_actions_do_the_right_thing(tmp_path: Path) -> None:
    state_file = tmp_path / "service_state.json"
    seen: list[str] = []

    def opener(_python: object = None) -> str:
        seen.append("open")
        return "opened"

    def scanner(_state: object = None) -> str:
        seen.append("scan")
        return "scanned"

    def stopper(_state: object = None) -> str:
        seen.append("stop")
        return "stopped"

    def starter(_state: object = None) -> str:
        seen.append("start")
        return "started"

    def exiter(_code: int = 0) -> None:
        seen.append("exit")

    dispatch(
        "open",
        state_file,
        opener=opener,
        scanner=scanner,
        stopper=stopper,
        starter=starter,
        exiter=exiter,
    )
    dispatch(
        "scan",
        state_file,
        opener=opener,
        scanner=scanner,
        stopper=stopper,
        starter=starter,
        exiter=exiter,
    )
    dispatch(
        "toggle",
        state_file,
        service_running=True,
        opener=opener,
        scanner=scanner,
        stopper=stopper,
        starter=starter,
        exiter=exiter,
    )
    dispatch(
        "toggle",
        state_file,
        service_running=False,
        opener=opener,
        scanner=scanner,
        stopper=stopper,
        starter=starter,
        exiter=exiter,
    )
    dispatch(
        "quit",
        state_file,
        opener=opener,
        scanner=scanner,
        stopper=stopper,
        starter=starter,
        exiter=exiter,
    )

    assert seen == ["open", "scan", "stop", "start", "stop", "exit"]


def test_an_unknown_action_does_nothing(tmp_path: Path) -> None:
    message = dispatch("nonsense", tmp_path / "state.json")
    assert "nothing" in message.lower()
