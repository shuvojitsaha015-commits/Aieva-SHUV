# Stop the Aieva background service.
#
#   .\scripts\stop_service.ps1
#
# It ends every Aieva service process (the watcher of the board and the
# floating window).
$ErrorActionPreference = "Stop"

# The command line of the process is needed to find the Aieva processes -
# Get-CimInstance knows it (Windows), Get-Process does not (Linux).
$processes = $null
if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
    $processes = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -like "*aieva.core.service*" }
} else {
    Write-Host "[aieva] this script needs Windows (Get-CimInstance)."
    exit 0
}

if (-not $processes) {
    Write-Host "[aieva] the background service is not running."
    exit 0
}

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "[aieva] the process $($process.ProcessId) was stopped."
}
