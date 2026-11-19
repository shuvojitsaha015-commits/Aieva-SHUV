"""The readiness check of Aieva.

``python -m aieva.core.doctor`` answers one question: **does this computer
read the board?** It checks the Python, the packages, the fog server, every
OCR engine, the capture of the board and the automatic start - and it says
exactly what to do when something is missing.

It is the first thing to run in a classroom, and the first thing to look at
when the teacher says "it does not work".
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The packages the product needs.
REQUIRED_PACKAGES: tuple[str, ...] = (
    "kivy",
    "sympy",
    "matplotlib",
    "numpy",
    "PIL",
    "fastapi",
    "uvicorn",
)

#: The name of the task of the Windows task scheduler.
TASK_NAME = "Aieva Background Service"

#: The signs of the report.
OK = "✓"
BAD = "✗"
WARN = "!"


@dataclass
class Check:
    """One line of the report."""

    name: str
    ok: bool
    detail: str = ""
    hint: str = ""
    optional: bool = False

    @property
    def sign(self) -> str:
        """The sign of the line."""
        if self.ok:
            return OK
        return WARN if self.optional else BAD

    def to_dict(self) -> dict[str, Any]:
        """The check as a plain dictionary."""
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "hint": self.hint,
            "optional": self.optional,
        }


@dataclass
class Report:
    """The whole report."""

    checks: list[Check] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        """Is everything that has to work really working?"""
        return all(check.ok for check in self.checks if not check.optional)

    @property
    def problems(self) -> list[Check]:
        """The checks that did not pass."""
        return [check for check in self.checks if not check.ok]

    def add(self, check: Check) -> None:
        """Put a check into the report."""
        self.checks.append(check)

    def to_dict(self) -> dict[str, Any]:
        """The report as a plain dictionary."""
        return {
            "ready": self.ready,
            "checks": [check.to_dict() for check in self.checks],
        }

    def render(self) -> str:
        """The report for the terminal."""
        lines = ["", "Aieva - is this computer ready for the board?", "=" * 58]
        for check in self.checks:
            lines.append(f"{check.sign} {check.name}")
            if check.detail:
                lines.append(f"    {check.detail}")
            if not check.ok and check.hint:
                lines.append(f"    -> {check.hint}")
        lines.append("=" * 58)
        if self.ready:
            lines.append("READY - the board is read in the background.")
        else:
            lines.append("NOT READY - these have to be fixed:")
            for check in self.problems:
                lines.append(f"  - {check.name}: {check.hint or 'see above'}")
        lines.append("")
        return "\n".join(lines)


# --------------------------------------------------------------------- checks
def check_python() -> Check:
    """Is the Python new enough?"""
    version = platform.python_version()
    ok = sys.version_info >= (3, 11)
    return Check(
        name="Python",
        ok=ok,
        detail=f"{version} ({platform.python_implementation()})",
        hint="Python 3.11 or newer is needed.",
    )


def check_packages() -> Check:
    """Are the packages of the product there?"""
    missing: list[str] = []
    for name in REQUIRED_PACKAGES:
        module = "PIL" if name == "PIL" else name
        try:
            __import__(module)
        except Exception:  # noqa: BLE001 - any import problem means "missing"
            missing.append(name)
    if missing:
        return Check(
            name="The packages of Aieva",
            ok=False,
            detail=f"missing: {', '.join(missing)}",
            hint="pip install -r requirements.txt -r requirements-server.txt",
        )
    return Check(
        name="The packages of Aieva",
        ok=True,
        detail=f"{len(REQUIRED_PACKAGES)} packages are there",
    )


def check_env() -> Check:
    """Is the .env there and does it have a key?"""
    from aieva.config import get_settings

    path = Path(__file__).resolve().parents[2] / ".env"
    settings = get_settings()
    if not path.is_file():
        return Check(
            name="The .env file",
            ok=False,
            detail=f"{path} is missing",
            hint="copy .env.example to .env and put the GEMINI_API_KEY into it",
        )
    if settings.has_gemini_key:
        return Check(
            name="The .env file",
            ok=True,
            detail=f"{path} - the Gemini key is there",
        )
    return Check(
        name="The .env file",
        ok=True,
        optional=True,
        detail=f"{path} - no Gemini key (the mock mode answers)",
        hint="without the key the cloud OCR is not possible",
    )


def check_server() -> Check:
    """Is the fog server there?"""
    from aieva.config import get_settings

    url = get_settings().server_url
    try:
        import httpx

        response = httpx.get(f"{url}/health", timeout=3.0)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - the server may be down
        return Check(
            name="The fog server (the cloud)",
            ok=False,
            optional=True,
            detail=f"{url} does not answer ({type(exc).__name__})",
            hint="start it with .\\scripts\\run_server.ps1 - Gemini reads the board",
        )
    mode = payload.get("mock", "?")
    return Check(
        name="The fog server (the cloud)",
        ok=True,
        optional=not mode,
        detail=f"{url} answers (mode: {mode})",
        hint=(
            "the server runs in the mock mode - put a GEMINI_API_KEY into the .env" if mode else ""
        ),
    )


def check_ocr(server_ok: bool = False) -> list[Check]:
    """Can the board be read? (Gemini is the engine of Aieva)."""
    from aieva.config import get_settings
    from aieva.core.ocr.engines import GeminiOcr

    checks: list[Check] = []
    settings = get_settings()

    gemini = GeminiOcr()
    configured = gemini.available()
    keys = settings.all_gemini_keys
    has_key = bool(keys)
    count = len(keys)

    if not configured:
        detail = "no server configured"
        hint = "put AIEVA_SERVER_URL into the .env"
    elif not server_ok:
        detail = "the server does not answer right now"
        hint = "start the fog server: .\\scripts\\run_server.ps1"
    elif not has_key:
        detail = "the server answers, but there is no Gemini key"
        hint = "put the GEMINI_API_KEY into the .env (the server needs it)"
    elif count > 1:
        detail = f"the server answers and {count} Gemini keys are there"
        hint = ""
    else:
        detail = "the server answers and the key is there"
        hint = ""

    checks.append(
        Check(
            name="OCR: Gemini (the engine of Aieva)",
            ok=configured and server_ok and has_key,
            detail=detail,
            hint=hint,
        )
    )

    checks.append(
        Check(
            name="The OCR of the board",
            ok=configured and server_ok and has_key,
            detail=(
                "the board is read by Gemini"
                if configured and server_ok and has_key
                else "the board cannot be read yet"
            ),
            hint="Aieva needs the server and the Gemini key - there is no offline version.",
        )
    )
    return checks


def check_capture() -> Check:
    """Can the service see the board?"""
    from aieva.core.ocr.capture import DesktopScreenSource
    from aieva.core.service.sources import FolderSource

    desktop = DesktopScreenSource()
    folder = FolderSource("ocr_inbox")
    if desktop.available():
        return Check(
            name="The capture of the board",
            ok=True,
            detail="the screen of this computer can be read",
        )
    if folder.available():
        return Check(
            name="The capture of the board",
            ok=True,
            detail=f"the folder {folder.folder} is watched",
            hint="the board has to share its screen into this folder",
        )
    return Check(
        name="The capture of the board",
        ok=False,
        detail="neither a screen nor a folder with pictures",
        hint="create the folder ocr_inbox or run the service on a computer with a screen",
    )


def check_autostart() -> Check:
    """Does the service start with the computer?"""
    if not sys.platform.startswith("win"):
        return Check(
            name="The automatic start",
            ok=False,
            optional=True,
            detail="Aieva starts automatically on Windows only",
            hint="",
        )
    if shutil.which("schtasks") is None:
        return Check(
            name="The automatic start",
            ok=False,
            optional=True,
            detail="schtasks was not found",
            hint="run: .\\scripts\\install_autostart.ps1",
        )
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Check(
            name="The automatic start",
            ok=False,
            optional=True,
            detail=f"could not be checked ({exc})",
            hint="run: .\\scripts\\install_autostart.ps1",
        )
    if result.returncode == 0:
        trigger = _trigger_of(result.stdout)
        return Check(
            name="The automatic start",
            ok=True,
            detail=f"the task '{TASK_NAME}' is registered ({trigger})",
        )

    # no task scheduler: the startup folder of the user does the job
    from aieva.core.service.autostart import startup_folder_path

    script = startup_folder_path() / "Aieva.cmd"
    if script.is_file():
        return Check(
            name="The automatic start",
            ok=True,
            detail=f"the startup file {script} is there",
        )
    return Check(
        name="The automatic start",
        ok=False,
        optional=True,
        detail="the service does not start with the computer",
        hint="run: .\\scripts\\install_autostart.ps1",
    )


def _trigger_of(output: str) -> str:
    """When does the task start? (the answer of ``schtasks /Query``)"""
    text = (output or "").lower()
    if "at system startup" in text or "onstart" in text:
        return "it starts when the computer boots"
    if "at logon" in text or "onlogon" in text:
        return "it starts when the teacher logs in"
    return "the trigger could not be read"


def check_service() -> Check:
    """Is the background service running right now?"""
    from aieva.core.service.config import ServiceConfig
    from aieva.core.service.state import ServiceState

    config = ServiceConfig.from_env()
    state = ServiceState.load(config.state_file)
    if state.is_running():
        return Check(
            name="The background service",
            ok=True,
            detail=f"it is running ({state.runs} readings so far)",
        )
    return Check(
        name="The background service",
        ok=False,
        optional=True,
        detail="it is not running",
        hint="start it with .\\scripts\\start_service.ps1",
    )


# ---------------------------------------------------------------------- report
def build_report() -> Report:
    """Run every check and collect the result."""
    report = Report()
    report.add(check_python())
    report.add(check_packages())
    report.add(check_env())
    server = check_server()
    report.add(server)
    for check in check_ocr(server_ok=server.ok):
        report.add(check)
    report.add(check_capture())
    report.add(check_autostart())
    report.add(check_service())
    return report


def main(argv: list[str] | None = None) -> int:
    """The entry point of the check."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="aieva-doctor", description="Is this computer ready to read the board?"
    )
    parser.add_argument("--json", action="store_true", help="the report as JSON")
    args = parser.parse_args(argv)

    report = build_report()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(report.render())
    return 0 if report.ready else 1


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())


__all__ = [
    "BAD",
    "OK",
    "REQUIRED_PACKAGES",
    "TASK_NAME",
    "WARN",
    "Check",
    "Report",
    "build_report",
    "check_autostart",
    "check_capture",
    "check_env",
    "check_ocr",
    "check_packages",
    "check_python",
    "check_server",
    "check_service",
    "main",
]
