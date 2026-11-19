"""The Windows scripts of the classroom computer.

PowerShell cannot be run in the test, so the scripts are checked the way a
teacher would notice a mistake: the file has to exist, the brackets have to
match, and the important helpers have to be in it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

#: The scripts the classroom computer needs.
REQUIRED = (
    "_python.ps1",
    "setup.ps1",
    "run_app.ps1",
    "run_server.ps1",
    "start_service.ps1",
    "stop_service.ps1",
    "install_autostart.ps1",
)


@pytest.mark.parametrize("name", REQUIRED)
def test_the_script_is_there(name: str) -> None:
    path = SCRIPTS / name
    assert path.is_file(), f"{name} is missing"
    assert path.stat().st_size > 0


@pytest.mark.parametrize("name", REQUIRED)
def test_the_brackets_match(name: str) -> None:
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    assert text.count("{") == text.count("}"), f"the brackets of {name} do not match"
    assert text.count("(") == text.count(")"), f"the parentheses of {name} do not match"


@pytest.mark.parametrize("name", REQUIRED)
def test_the_script_is_utf8_and_has_a_newline(name: str) -> None:
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    assert text.endswith("\n")
    # Windows line endings are allowed - the scripts are read as UTF-8.
    assert text.encode("utf-8").decode("utf-8") == text


def test_the_python_helper_finds_the_venv() -> None:
    text = (SCRIPTS / "_python.ps1").read_text(encoding="utf-8")
    assert ".venv" in text
    assert "python.exe" in text
    assert "function Get-AievaPython" in text
    assert "function Test-AievaReady" in text
    assert "function Test-AievaPort" in text


def test_the_setup_creates_the_venv() -> None:
    text = (SCRIPTS / "setup.ps1").read_text(encoding="utf-8")
    assert "python -m venv .venv" in text
    assert "requirements.txt" in text
    assert ".env.example" in text


def test_the_setup_asks_for_the_gemini_key() -> None:
    """The OCR of Aieva is Gemini - the network and the key are needed."""
    text = (SCRIPTS / "setup.ps1").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY" in text
    assert "Tesseract" not in text, "the local OCR is not part of Aieva any more"


def test_the_app_uses_the_venv() -> None:
    text = (SCRIPTS / "run_app.ps1").read_text(encoding="utf-8")
    assert "_python.ps1" in text
    assert "Get-AievaPython" in text
    assert "aieva.ui.app" in text


def test_the_server_does_not_start_twice() -> None:
    text = (SCRIPTS / "run_server.ps1").read_text(encoding="utf-8")
    assert "Test-AievaPort" in text
    assert "already in use" in text


def test_the_service_starts_without_a_window() -> None:
    text = (SCRIPTS / "start_service.ps1").read_text(encoding="utf-8")
    assert "aieva.core.service" in text
    assert "pythonw.exe" in text


def test_the_autostart_registers_the_task() -> None:
    text = (SCRIPTS / "install_autostart.ps1").read_text(encoding="utf-8")
    assert "install-autostart" in text


def test_the_autostart_tries_the_boot_first() -> None:
    """The requirement: the service starts when the computer boots.

    Without a switch the application chooses - the boot first, the login as
    the fallback. ``-OnLogon`` forces the variant without administrator
    rights.
    """
    text = (SCRIPTS / "install_autostart.ps1").read_text(encoding="utf-8")
    assert "boot" in text.lower()
    assert "OnLogon" in text
    assert "onlogon" in text.lower()
