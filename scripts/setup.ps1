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
. (Join-Path $PSScriptRoot "_python.ps1")

Write-Host "[aieva] creating the virtual environment..."
$venvPython = Join-Path ".venv" "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    # Python has to be on the PATH - otherwise the school computer has no
    # way to build the environment.
    $systemPython = Get-Command python -ErrorAction SilentlyContinue
    if (-not $systemPython) {
        $systemPython = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $systemPython) {
        Write-Host ""
        Write-Host "[aieva] Python was not found on this computer."
        Write-Host "[aieva] Install Python 3.11 or newer from https://www.python.org/downloads/"
        Write-Host "[aieva] and tick 'Add python.exe to PATH' during the installation."
        Write-Host "[aieva] Then run this script again."
        exit 1
    }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $systemPython.Source -m venv .venv 2>&1 | Write-AievaOutput
    } finally {
        $ErrorActionPreference = $previous
    }
    if (-not (Test-Path $venvPython)) {
        Write-Host "[aieva] the virtual environment could not be created - see the message above."
        exit 1
    }
}

$python = (Resolve-Path $venvPython).Path
Write-Host "[aieva] installing the packages (this takes a few minutes)..."

# pip writes its progress to stderr - PowerShell would call that an error
# and (with $ErrorActionPreference = "Stop") stop the script, so the output
# is merged here.
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python -m pip install --upgrade pip 2>&1 | Write-AievaOutput
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[aieva] pip could not be updated - is the computer online?"
        exit 1
    }
    & $python -m pip install -r requirements.txt -r requirements-server.txt -r requirements-dev.txt 2>&1 | Write-AievaOutput
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[aieva] the installation failed - the message above says why."
        exit 1
    }
} finally {
    $ErrorActionPreference = $previous
}

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
Write-Host ""
Write-Host "[aieva] the packages are about 190 MB - the first installation takes"
Write-Host "[aieva] a few minutes. Do not close this window while it works."
