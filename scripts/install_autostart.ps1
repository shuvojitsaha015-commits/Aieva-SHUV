# Let the Aieva background service start with the computer.
#
#   .\scripts\install_autostart.ps1
#
# The service is registered as a task of the Windows task scheduler. It
# starts when somebody logs in ("onlogon", no administrator rights needed).
# Use -OnStart to start it when the computer boots (administrator rights
# needed).
param(
    [switch]$OnStart
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
$trigger = if ($OnStart) { "onstart" } else { "onlogon" }

& $python -m aieva.core.service install-autostart --trigger $trigger
