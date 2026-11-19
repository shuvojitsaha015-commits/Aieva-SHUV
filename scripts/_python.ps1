# Finds the Python interpreter of the project and runs it safely.
#
# Every Windows script of Aieva uses this file, so the **same** interpreter
# is used everywhere: the virtual environment first, then the Python of the
# system. That is what stops "No module named 'kivy'" - the venv is used
# automatically, nobody has to activate it by hand.

function Get-AievaVenvPath {
    # The Scripts folder of the virtual environment.
    return (Join-Path (Join-Path $PSScriptRoot "..") ".venv")
}

function Get-AievaPython {
    # The interpreter of the project (the virtual environment first).
    $exe = Join-Path (Get-AievaVenvPath) "Scripts\python.exe"
    if (Test-Path $exe) { return (Resolve-Path $exe).Path }
    foreach ($name in @("python.exe", "py.exe")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    return $null
}

function Get-AievaPythonw {
    # The interpreter without a console window (the background service).
    $exe = Join-Path (Get-AievaVenvPath) "Scripts\pythonw.exe"
    if (Test-Path $exe) { return (Resolve-Path $exe).Path }
    return (Get-AievaPython)
}

function Invoke-AievaPython {
    # Runs the interpreter of the project without letting it break the script.
    #
    # PowerShell turns a message on stderr of a native command into an error
    # record - and with $ErrorActionPreference = "Stop" that error stops
    # everything. Kivy and pip write their log to stderr, so every native
    # call of Aieva goes through this helper: the output is shown as normal
    # text and the exit code comes back.
    param(
        [string[]]$Arguments = @(),
        [switch]$Quiet
    )

    $python = Get-AievaPython
    if (-not $python) {
        Write-Host "[aieva] Python was not found - install Python 3.11 or newer."
        return 1
    }

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($Quiet) {
            & $python @Arguments *> $null
        } else {
            & $python @Arguments 2>&1 | Write-AievaOutput
        }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Write-AievaOutput {
    # Prints the output of a native command as normal text.
    #
    # A message on stderr arrives as an error record; without this helper
    # PowerShell writes "System.Management.Automation.RemoteException" in the
    # middle of the log of the program.
    param([Parameter(ValueFromPipeline = $true)]$Item)
    process {
        if ($Item -is [System.Management.Automation.ErrorRecord]) {
            Write-Host $Item.Exception.Message
        } else {
            Write-Host $Item
        }
    }
}

function Test-AievaPackage {
    # Is the package there? Only the exit code matters.
    #
    # The child is started with .NET and its output is caught with pipes:
    # PowerShell must NOT see the message on stderr. On Windows PowerShell
    # 5.1 a native command that writes to stderr becomes an error record,
    # and with $ErrorActionPreference = "Stop" that error stops the whole
    # script (the log of Kivy is such a message).
    param([string]$Python, [string]$Package)

    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $Python
    $info.Arguments = "-c `"import $Package`""
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true

    $process = [System.Diagnostics.Process]::Start($info)
    # both streams are read before the wait - a full pipe would block the child
    $process.StandardOutput.ReadToEnd() | Out-Null
    $process.StandardError.ReadToEnd() | Out-Null
    $process.WaitForExit(120000) | Out-Null
    return ($process.ExitCode -eq 0)
}

function Test-AievaReady {
    # Check that Python and the given packages are there.
    # The param block has to be the FIRST statement of the function: a string
    # before it would turn "param" into a command and break the whole script.
    param([string[]]$Packages = @())

    $python = Get-AievaPython
    if (-not $python) {
        Write-Host "[aieva] Python was not found - install Python 3.11 or newer."
        return $false
    }

    foreach ($package in $Packages) {
        if (-not (Test-AievaPackage -Python $python -Package $package)) {
            Write-Host "[aieva] the package '$package' is missing in $python."
            Write-Host "[aieva] one command fixes it:  .\scripts\setup.ps1"
            return $false
        }
    }
    return $true
}

function Test-AievaPort {
    # Is somebody already listening on the port? (returns the PID or $null).
    param([int]$Port = 8000)
    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($connection) { return $connection[0].OwningProcess }
    } catch {
        return $null
    }
    return $null
}
