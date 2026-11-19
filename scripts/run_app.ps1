# Start the Aieva Kivy application on Windows.
#
#   .\scripts\run_app.ps1
#
# The script always uses the virtual environment of the project, so the
# application starts even when the shell was never activated.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "_python.ps1")

if (-not (Test-AievaReady -Packages @("kivy", "sympy", "matplotlib"))) { exit 1 }

$python = Get-AievaPython
Write-Host "[aieva] starting the application with $python"
& $python -m aieva.ui.app @args
