# Start the Aieva Kivy application on Windows.
#
#   .\scripts\run_app.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m aieva.ui.app @args
