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
. (Join-Path $PSScriptRoot "_python.ps1")

$python = Get-AievaPythonw
if (-not $python) {
    Write-Host "[aieva] Python was not found - install it or run .\scripts\setup.ps1"
    exit 1
}

$arguments = @("-m", "aieva.core.service", "install-autostart")
if ($OnLogon) { $arguments += @("--trigger", "onlogon") }
if ($WithWindow) { $arguments += "--with-window" }

# The installer of the task writes to stderr when it falls back to another
# method - that must not stop the script.
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python @arguments 2>&1 | Write-AievaOutput
    $code = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}

if ($code -ne 0) {
    Write-Host ""
    Write-Host "[aieva] the task was not registered - the message above says why."
    exit $code
}

Write-Host ""
Write-Host "[aieva] the board service now starts with the computer."
Write-Host "[aieva] to check it:  .\.venv\Scripts\python.exe -m aieva.core.doctor"
Write-Host "[aieva] restart the computer and watch the board - the control"
Write-Host "[aieva] with 'Scan' has to be there without any typing."
Write-Host "[aieva] the icon of Aieva is in the system tray - it opens the app."
