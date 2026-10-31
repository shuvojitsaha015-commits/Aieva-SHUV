# Start the Aieva fog server (FastAPI + uvicorn) on Windows.
#
#   .\scripts\run_server.ps1
#
# Without a GEMINI_API_KEY the server answers with the mock data.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$bind = if ($env:AIEVA_SERVER_HOST) { $env:AIEVA_SERVER_HOST } else { "0.0.0.0" }
$port = if ($env:AIEVA_SERVER_PORT) { $env:AIEVA_SERVER_PORT } else { "8000" }

Write-Host "[aieva] server listening on http://${bind}:${port}  (docs: /docs, health: /health)"
python -m uvicorn server.main:app --host $bind --port $port @args
