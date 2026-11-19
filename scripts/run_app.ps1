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

# Kivy writes its log to stderr. PowerShell would call that an error and
# (with $ErrorActionPreference = "Stop") stop the script, so the log is
# merged into the normal output and the preference is only lowered for the
# time of the call.
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python -m aieva.ui.app @args 2>&1 | Write-AievaOutput
    $code = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}

if ($code -ne 0) {
    Write-Host "[aieva] the application stopped with the code $code."
}
exit $code
