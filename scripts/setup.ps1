# Set the Aieva project up on a computer (one command).
#
#   .\scripts\setup.ps1
#
# It creates the virtual environment, installs everything and writes the
# .env file. Run it once on a new classroom computer - after that the
# background service can be installed with:
#
#   .\scripts\install_autostart.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "[aieva] creating the virtual environment..."
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

$python = (Resolve-Path ".venv\Scripts\python.exe").Path
Write-Host "[aieva] installing the packages..."
& $python -m pip install --upgrade pip --quiet
& $python -m pip install -r requirements.txt -r requirements-server.txt -r requirements-dev.txt --quiet

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[aieva] the .env was written - put your GEMINI_API_KEY into it."
}

# The OCR of Aieva is Gemini (it reads the board through the fog server).
# The network and the key are needed - there is no offline version.
$key = $null
if (Test-Path ".env") {
    $line = Select-String -Path ".env" -Pattern "^GEMINI_API_KEY=(.+)$" | Select-Object -First 1
    if ($line) { $key = $line.Matches[0].Groups[1].Value.Trim() }
}
if ($key) {
    Write-Host "[aieva] the Gemini key is in the .env - the board can be read."
} else {
    Write-Host ""
    Write-Host "[aieva] there is no GEMINI_API_KEY in the .env yet."
    Write-Host "[aieva] Aieva reads the board with Gemini - it needs the key"
    Write-Host "[aieva] and a connection to the internet. Put the key into .env:"
    Write-Host "        GEMINI_API_KEY=your-key-here"
}

Write-Host ""
Write-Host "[aieva] the setup is done. Now:"
Write-Host "   .\scripts\install_autostart.ps1   # the board starts on its own"
Write-Host "   .\scripts\start_service.ps1      # or start it by hand"
Write-Host "   .\scripts\run_app.ps1             # the window of the teacher"
Write-Host ""
Write-Host "[aieva] the check of the readiness:  .\.venv\Scripts\python.exe -m aieva.core.doctor"
