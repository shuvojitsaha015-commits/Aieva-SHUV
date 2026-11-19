"""The PowerShell scripts of the classroom computer - really executed.

The GitHub runner (ubuntu) has PowerShell, so the scripts are not only read
here - they are parsed and run. That is how the two bugs of the Windows
scripts were found:

* a ``param`` block that was not the first statement of a function (the
  docstrings of Python are statements in PowerShell), and
* a native command whose message on stderr stopped the whole script
  (``$ErrorActionPreference = "Stop"`` + the log of Kivy on stderr).

The tests are skipped when PowerShell is not on the machine.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

#: Every PowerShell file of the project.
ALL_SCRIPTS = sorted(SCRIPTS.glob("*.ps1"))

#: The script that holds the shared helpers.
HELPER = SCRIPTS / "_python.ps1"


def _pwsh() -> str | None:
    """The PowerShell of the machine (or None)."""
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    return None


PWSH = _pwsh()

needs_pwsh = pytest.mark.skipif(PWSH is None, reason="PowerShell is not on this machine")


def _run(script: str) -> subprocess.CompletedProcess[str]:
    """Run a piece of PowerShell and return the result."""
    assert PWSH is not None
    return subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(SCRIPTS.parent),
    )


@needs_pwsh
@pytest.mark.parametrize("path", ALL_SCRIPTS, ids=lambda p: p.name)
def test_the_script_has_no_syntax_error(path: Path) -> None:
    """PowerShell itself parses the file - a mistake would be reported."""
    assert PWSH is not None
    result = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "$errors = $null; $tokens = $null; "
                f"[System.Management.Automation.Language.Parser]::ParseFile('{path}', "
                "[ref]$tokens, [ref]$errors) | Out-Null; "
                "if ($errors) { $errors | ForEach-Object { $_.Message }; exit 1 }"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@needs_pwsh
@pytest.mark.parametrize("path", ALL_SCRIPTS, ids=lambda p: p.name)
def test_the_param_block_is_the_first_statement(path: Path) -> None:
    """``param`` as a command is the classic mistake of a PowerShell file.

    The parser does not report it - it only fails when the function is
    called. So the AST is asked for the commands called "param".
    """
    assert PWSH is not None
    result = _run(
        "$errors = $null; $tokens = $null; "
        f"$ast = [System.Management.Automation.Language.Parser]::ParseFile('{path}', "
        "[ref]$tokens, [ref]$errors); "
        "$ast.FindAll({ param($n) $n -is "
        "[System.Management.Automation.Language.CommandAst] -and $n.GetCommandName() -eq 'param' }, "
        "$true) | ForEach-Object { $_.Extent.StartLineNumber }"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "", (
        f"{path.name}: 'param' is used as a command on line {result.stdout.strip()} - "
        "it has to be the first statement of the block"
    )


@needs_pwsh
def test_the_helper_runs_without_a_python() -> None:
    """The helpers must not explode when there is no interpreter."""
    result = _run(f'. "{HELPER}"; "loaded"')
    assert result.returncode == 0, result.stdout + result.stderr
    assert "loaded" in result.stdout


@needs_pwsh
def test_the_helper_survives_a_message_on_stderr() -> None:
    """A native command that writes to stderr must not stop the script.

    This is the bug that broke ``run_app.ps1`` on Windows: PowerShell turns
    the log of Kivy (stderr) into an error and, with
    ``$ErrorActionPreference = "Stop"``, the script dies.
    """
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f'. "{HELPER}"\n'
        "$code = Invoke-AievaPython -Arguments @('-c', "
        "'import sys; sys.stderr.write(\"the log of the program\\n\")')\n"
        "'the script is still alive'"
    )
    result = _run(script)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "the script is still alive" in result.stdout
    assert "NativeCommandError" not in result.stdout + result.stderr


@needs_pwsh
def test_the_port_helper_works() -> None:
    """``Test-AievaPort`` must answer without an exception."""
    result = _run(f'. "{HELPER}"; $p = Test-AievaPort -Port 8000; "ok"')
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout
    assert "param" not in result.stderr.lower()
