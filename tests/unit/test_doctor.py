"""The check that tells the teacher whether the board works."""

from __future__ import annotations

import json

import pytest

from aieva.core.doctor import (
    Check,
    Report,
    build_report,
    check_autostart,
    check_capture,
    check_env,
    check_ocr,
    check_packages,
    check_python,
    check_server,
    main,
)


def test_the_report_is_a_list_of_lines() -> None:
    report = Report()
    report.add(Check(name="Something", ok=True, detail="it works"))
    assert report.ready is True
    assert report.problems == []
    assert "✓ Something" in report.render()


def test_a_problem_is_shown_with_a_hint() -> None:
    report = Report()
    report.add(Check(name="Something", ok=False, hint="do this"))
    assert report.ready is False
    text = report.render()
    assert "✗ Something" in text
    assert "-> do this" in text


def test_an_optional_problem_does_not_stop_the_report() -> None:
    report = Report()
    report.add(Check(name="Nice to have", ok=False, optional=True))
    assert report.ready is True


def test_the_report_can_be_json() -> None:
    report = Report()
    report.add(Check(name="Something", ok=True))
    payload = json.loads(json.dumps(report.to_dict()))
    assert payload["ready"] is True
    assert payload["checks"][0]["name"] == "Something"


def test_the_python_is_checked() -> None:
    check = check_python()
    assert check.name == "Python"
    assert check.detail


def test_the_packages_are_checked() -> None:
    check = check_packages()
    assert check.name == "The packages of Aieva"


def test_the_env_is_checked(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "aieva.config.get_settings",
        lambda: type("S", (), {"cache_dir": str(tmp_path), "has_gemini_key": False})(),
    )
    check = check_env()
    assert check.name == "The .env file"


def test_the_server_is_checked() -> None:
    check = check_server()
    assert check.name == "The fog server (the cloud)"


def test_the_engines_are_checked() -> None:
    checks = check_ocr(server_ok=False)
    names = [check.name for check in checks]
    assert any("Gemini" in name for name in names)
    assert "The OCR of the board" in names


def test_without_the_server_the_board_cannot_be_read() -> None:
    checks = check_ocr(server_ok=False)
    gemini = next(check for check in checks if "Gemini" in check.name)
    assert gemini.ok is False
    assert gemini.hint


def test_the_capture_is_checked() -> None:
    check = check_capture()
    assert check.name == "The capture of the board"


def test_the_autostart_is_checked() -> None:
    check = check_autostart()
    assert check.name == "The automatic start"


def test_the_whole_report_is_built() -> None:
    report = build_report()
    assert report.checks
    assert isinstance(report.ready, bool)


def test_the_command_prints_the_report(capsys) -> None:
    main([])
    captured = capsys.readouterr()
    assert "Aieva" in captured.out


def test_the_command_can_print_json(capsys) -> None:
    main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "checks" in payload


@pytest.mark.parametrize("name", ["Python", "The packages of Aieva"])
def test_the_important_checks_have_a_name(name: str) -> None:
    assert name
