# Stop the Aieva background service.
#
#   .\scripts\stop_service.ps1
#
# It ends every Aieva service process (the watcher of the board and the
# floating window).
$ErrorActionPreference = "Stop"

$processes = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*aieva.core.service*" }

if (-not $processes) {
    Write-Host "[aieva] the background service is not running."
    exit 0
}

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "[aieva] the process $($process.ProcessId) was stopped."
}
