# Let the Aieva background service start with the computer.
#
#   .\scripts\install_autostart.ps1
#
# The service is registered as a task of the Windows task scheduler. It
# starts when the computer **boots** ("ONSTART"). That needs administrator
# rights - when they are missing the task falls back to the login
# ("ONLOGON") and then to the startup folder of the user. The script says
# which one was used.
#
# Use -WithWindow to start the full application too (the teacher normally
# opens it from the icon in the system tray).
param(
    [switch]$OnLogon,
    [switch]$WithWindow
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Get-AievaPython {
    $candidates = @(
        (Join-Path $PSScriptRoot "..\.venv\Scripts\pythonw.exe"),
        (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return (Resolve-Path $candidate).Path }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    Write-Error "Python was not found."
}

$python = Get-AievaPython

$arguments = @("-m", "aieva.core.service", "install-autostart")
if ($OnLogon) { $arguments += @("--trigger", "onlogon") }
if ($WithWindow) { $arguments += "--with-window" }

& $python @arguments

Write-Host ""
Write-Host "[aieva] the board service now starts with the computer."
Write-Host "[aieva] to check it:  .\.venv\Scripts\python.exe -m aieva.core.doctor"
Write-Host "[aieva] restart the computer and watch the board - the control"
Write-Host "[aieva] with 'Scan' has to be there without any typing."
Write-Host "[aieva] the icon of Aieva is in the system tray - it opens the app."
