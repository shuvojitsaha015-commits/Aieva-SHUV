# Start the Aieva fog server (FastAPI + uvicorn) on Windows.
#
#   .\scripts\run_server.ps1
#
# Without a GEMINI_API_KEY the server answers with the mock data.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "_python.ps1")

if (-not (Test-AievaReady -Packages @("uvicorn", "fastapi"))) { exit 1 }

$bind = if ($env:AIEVA_SERVER_HOST) { $env:AIEVA_SERVER_HOST } else { "0.0.0.0" }
$port = if ($env:AIEVA_SERVER_PORT) { [int]$env:AIEVA_SERVER_PORT } else { 8000 }

$busy = Test-AievaPort -Port $port
if ($busy) {
    Write-Host "[aieva] the port $port is already in use (PID $busy)."
    Write-Host "[aieva] the server is probably already running: http://127.0.0.1:$port/docs"
    Write-Host "[aieva] to stop it:  Stop-Process -Id $busy"
    exit 0
}

Write-Host "[aieva] server listening on http://${bind}:${port}  (docs: /docs, health: /health)"
$python = Get-AievaPython
& $python -m uvicorn server.main:app --host $bind --port $port @args
