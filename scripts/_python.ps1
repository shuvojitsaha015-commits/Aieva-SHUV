# Finds the Python interpreter of the project.
#
# Every Windows script of Aieva uses this file, so the **same** interpreter
# is used everywhere: the virtual environment first, then the Python of the
# system. That is what stops "No module named 'kivy'" - the venv is used
# automatically, nobody has to activate it by hand.

function Get-AievaVenvPath {
    """The Scripts folder of the virtual environment."""
    return (Join-Path $PSScriptRoot "..\.venv\Scripts")
}

function Get-AievaPython {
    """The interpreter of the project (the virtual environment first)."""
    $exe = Join-Path (Get-AievaVenvPath) "python.exe"
    if (Test-Path $exe) { return (Resolve-Path $exe).Path }
    foreach ($name in @("python.exe", "py.exe")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    return $null
}

function Get-AievaPythonw {
    """The interpreter without a console window (the background service)."""
    $exe = Join-Path (Get-AievaVenvPath) "pythonw.exe"
    if (Test-Path $exe) { return (Resolve-Path $exe).Path }
    return (Get-AievaPython)
}

function Test-AievaReady {
    """Check that Python and the given packages are there."""
    param([string[]]$Packages = @())

    $python = Get-AievaPython
    if (-not $python) {
        Write-Host "[aieva] Python was not found - install Python 3.11 or newer."
        return $false
    }
    foreach ($package in $Packages) {
        & $python -c "import $package" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[aieva] the package '$package' is missing in $python."
            Write-Host "[aieva] one command fixes it:  .\scripts\setup.ps1"
            return $false
        }
    }
    return $true
}

function Test-AievaPort {
    """Is somebody already listening on the port? (returns the PID or $null)"""
    param([int]$Port = 8000)
    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($connection) { return $connection[0].OwningProcess }
    } catch {
        return $null
    }
    return $null
}
