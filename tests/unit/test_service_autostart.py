"""Starting the service automatically with the computer."""

from aieva.core.service.autostart import (
    TASK_NAME,
    install_windows_task,
    launch_agent_text,
    launcher_text,
    remove_windows_task,
    systemd_unit_text,
    windows_task_arguments,
)


class FakeResult:
    """The answer of a command."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_the_launcher_starts_the_service() -> None:
    text = launcher_text("C:/py/pythonw.exe", "E:/aieva")
    assert "pythonw.exe" in text
    assert "aieva.core.service run" in text
    assert 'cd /d "E:/aieva"' in text


def test_the_task_starts_at_the_login() -> None:
    command = windows_task_arguments(trigger="onlogon")
    assert command[0] == "schtasks"
    assert "/Create" in command
    assert "ONLOGON" in command
    assert TASK_NAME in command


def test_the_task_can_start_with_the_computer() -> None:
    assert "ONSTART" in windows_task_arguments(trigger="onstart")


def test_an_unknown_trigger_falls_back_to_the_login() -> None:
    assert "ONLOGON" in windows_task_arguments(trigger="whenever")


def test_installing_the_task(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    calls: list[list[str]] = []

    def runner(command, **_kwargs):
        calls.append(command)
        return FakeResult()

    message = install_windows_task(python_exe="python", project_dir=tmp_path, runner=runner)
    assert calls
    assert "/Create" in calls[0]
    assert (tmp_path / "Aieva" / "run_service.cmd").is_file()
    assert "The task was created." in message


def test_a_failing_task_is_reported(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    def runner(command, **_kwargs):
        return FakeResult(returncode=1, stderr="access denied")

    message = install_windows_task(python_exe="python", project_dir=tmp_path, runner=runner)
    assert "could not be created" in message
    assert "access denied" in message


def test_removing_the_task() -> None:
    calls: list[list[str]] = []

    def runner(command, **_kwargs):
        calls.append(command)
        return FakeResult()

    message = remove_windows_task(runner=runner)
    assert "/Delete" in calls[0]
    assert "The task was removed." in message


def test_the_systemd_unit_starts_the_service() -> None:
    unit = systemd_unit_text("/home/board/aieva", "/usr/bin/python3")
    assert "[Service]" in unit
    assert "WorkingDirectory=/home/board/aieva" in unit
    assert "aieva.core.service run" in unit
    assert "Restart=on-failure" in unit


def test_the_launch_agent_starts_the_service() -> None:
    agent = launch_agent_text("/home/board/aieva", "/usr/bin/python3")
    assert "com.aieva.board-service" in agent
    assert "aieva.core.service run" in agent
    assert "<true/>" in agent
