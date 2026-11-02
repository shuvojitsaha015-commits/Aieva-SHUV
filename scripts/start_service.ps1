# Start the Aieva background service (the smart board application).
#
#   .\scripts\start_service.ps1
#   .\scripts\start_service.ps1 -Overlay     # with the floating window
#   .\scripts\start_service.ps1 -Mock        # without the cloud (for a demo)
#
# The service runs in the background: it watches the board, reads what is
# written there, solves it and draws the graph. No window is opened and the
# terminal can be closed right away.
param(
    [switch]$Mock,
    [switch]$Overlay,
    [int]$Interval = 2,
    [switch]$Wait
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
    $command = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    Write-Error "Python was not found - install it or create the virtual environment."
}

$python = Get-AievaPython
$arguments = @("-m", "aieva.core.service", "run", "--interval", $Interval)
if ($Mock) { $arguments += "--mock" }
if ($Overlay) { $arguments += "--overlay" }

if ($Wait) {
    & $python @arguments
    exit $LASTEXITCODE
}

Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory (Get-Location).Path
Write-Host "[aieva] the background service is starting - it watches the board every $Interval s."
Write-Host "[aieva] the status:  python -m aieva.core.service status"
Write-Host "[aieva] the stop:    .\scripts\stop_service.ps1"
