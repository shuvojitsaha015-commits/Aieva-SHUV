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
. (Join-Path $PSScriptRoot "_python.ps1")

# The background service runs without a console window (pythonw.exe).
$python = Get-AievaPythonw
if (-not $python) {
    Write-Host "[aieva] Python was not found - install it or run .\scripts\setup.ps1"
    exit 1
}

$arguments = @("-m", "aieva.core.service", "run", "--interval", $Interval)
if ($Mock) { $arguments += "--mock" }
if ($Overlay) { $arguments += "--overlay" }

if ($Wait) {
    # The service stays in the foreground - the log of the board is shown.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $python @arguments 2>&1 | Write-AievaOutput
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    exit $code
}

Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory (Get-Location).Path
Write-Host "[aieva] the background service is starting - it watches the board every $Interval s."
Write-Host "[aieva] the status:  python -m aieva.core.service status"
Write-Host "[aieva] the stop:    .\scripts\stop_service.ps1"
