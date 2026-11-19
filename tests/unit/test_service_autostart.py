"""Starting the service automatically with the computer."""

from aieva.core.service.autostart import (
    TASK_NAME,
    install_windows_task,
    launcher_text,
    remove_windows_task,
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


def test_the_task_can_start_with_the_computer_at_the_boot() -> None:
    """Aieva has to run before anybody logs in."""
    command = windows_task_arguments(trigger="onstart")
    assert "ONSTART" in command


def test_the_launcher_can_start_the_window_of_the_teacher() -> None:
    from aieva.core.service.autostart import launcher_text

    text = launcher_text("pythonw.exe", "C:/aieva", "--overlay", with_window=True)
    assert "aieva.core.service run" in text
    assert "aieva.ui.app" in text


def test_the_launcher_without_the_window_has_only_the_service() -> None:
    from aieva.core.service.autostart import launcher_text

    text = launcher_text("pythonw.exe", "C:/aieva", "--overlay")
    assert "aieva.core.service run" in text
    assert "aieva.ui.app" not in text


def test_the_task_starts_the_overlay() -> None:
    from aieva.core.service.autostart import launcher_text

    text = launcher_text("pythonw.exe", "C:/aieva", "--overlay")
    assert "--overlay" in text


def test_the_startup_folder_starts_aieva() -> None:
    """Without administrator rights the startup folder does the job."""
    from aieva.core.service.autostart import startup_script_text

    text = startup_script_text("C:/aieva/.venv/Scripts/pythonw.exe", "C:/aieva", "--overlay")
    assert "pythonw.exe" in text
    assert "aieva.core.service run" in text
    assert 'cd /d "C:/aieva"' in text


def test_the_startup_file_is_written(tmp_path, monkeypatch) -> None:
    from aieva.core.service.autostart import install_startup_folder, startup_folder_path

    monkeypatch.setenv("APPDATA", str(tmp_path))
    message = install_startup_folder(python_exe="python", project_dir=tmp_path)
    assert (startup_folder_path() / "Aieva.cmd").is_file()
    assert "startup file" in message


def test_the_startup_file_can_be_removed(tmp_path, monkeypatch) -> None:
    from aieva.core.service.autostart import (
        install_startup_folder,
        remove_startup_folder,
        startup_folder_path,
    )

    monkeypatch.setenv("APPDATA", str(tmp_path))
    install_startup_folder(python_exe="python", project_dir=tmp_path)
    remove_startup_folder()
    assert not (startup_folder_path() / "Aieva.cmd").is_file()


def test_the_launcher_shows_the_icon_in_the_system_tray() -> None:
    """The board PC gets the icon of Aieva when the service starts."""
    text = launcher_text("C:/py/pythonw.exe", "C:/aieva", "--overlay")
    assert "--tray" in text


def test_the_tray_is_not_added_twice() -> None:
    text = launcher_text("C:/py/pythonw.exe", "C:/aieva", "--overlay --tray")
    assert text.count("--tray") == 1


def test_the_tray_can_be_left_out() -> None:
    text = launcher_text("C:/py/pythonw.exe", "C:/aieva", "--overlay", with_tray=False)
    assert "--tray" not in text


def test_the_task_is_created_for_the_boot(monkeypatch) -> None:
    """The requirement: the service starts when the computer boots."""
    monkeypatch.setattr("sys.platform", "win32")
    commands: list[list[str]] = []

    def runner(command, **kwargs):
        commands.append(command)
        return FakeResult(returncode=0, stdout="SUCCESS")

    from aieva.core.service.autostart import install_autostart

    message = install_autostart(trigger="onstart", runner=runner)
    assert "ONSTART" in " ".join(commands[0])
    assert "created" in message.lower()


def test_the_boot_is_tried_first_and_the_login_is_the_fallback(monkeypatch) -> None:
    """Without administrator rights the login is used instead."""
    monkeypatch.setattr("sys.platform", "win32")
    commands: list[list[str]] = []

    def runner(command, **kwargs):
        commands.append(command)
        if "ONSTART" in command:
            return FakeResult(returncode=1, stderr="ERROR: Access is denied.")
        return FakeResult(returncode=0, stdout="SUCCESS")

    from aieva.core.service.autostart import install_with_fallback

    message = install_with_fallback(runner=runner)
    assert "ONSTART" in commands[0]
    assert "ONLOGON" in commands[1]
    assert "logs in" in message


def test_the_startup_folder_is_the_last_way_out(monkeypatch) -> None:
    """When the task scheduler refuses both, the startup folder does it."""
    monkeypatch.setattr("sys.platform", "win32")
    commands: list[list[str]] = []

    def runner(command, **kwargs):
        commands.append(command)
        return FakeResult(returncode=1, stderr="ERROR: Access is denied.")

    from aieva.core.service import autostart as autostart_module

    original = autostart_module.install_startup_folder
    autostart_module.install_startup_folder = lambda **kwargs: "The startup file was written."  # type: ignore[assignment]
    try:
        message = autostart_module.install_with_fallback(runner=runner)
    finally:
        autostart_module.install_startup_folder = original  # type: ignore[assignment]

    assert "startup file" in message.lower()
