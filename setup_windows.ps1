### Rohde & Schwarz Automation for demonstration use.
### Title  : Sets up the Python environment for xdw_file_playback.py on Windows.
###           Creates a virtual environment in .venv and installs requirements.txt into it.
### Usage  : Open PowerShell in the repository folder and run
###               powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
###           Add -Recreate to delete .venv and start over.
###           Add -Python <path> to choose the interpreter, e.g. -Python C:\Python312\python.exe
###           Requires Python 3.12 or later (3.12 recommended).
param(
    [switch]$Recreate,
    [string]$Python
)
$ErrorActionPreference = 'Stop'

Set-Location -Path $PSScriptRoot
$VenvDir = '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

# Runs a native command and stops the script if it fails
function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    # Exit codes are checked instead: in Windows PowerShell 5.1, 'Stop' can abort on harmless stderr output
    $ErrorActionPreference = 'Continue'
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit code $LASTEXITCODE): $Exe $($Arguments -join ' ')"
    }
}

# numpy 2.5.3 requires Python 3.12 or later; prefer 3.12, the version verified with the user guide
$PyCheck = 'import sys; sys.exit(sys.version_info < (3, 12))'

# Returns $true if the command (exe + arguments) starts a supported Python version
function Test-Python {
    param([string]$Exe, [string[]]$Arguments)
    $ErrorActionPreference = 'Continue'
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) { return $false }
    # 'python' can be the Microsoft Store placeholder, which only opens the Store; this check rejects it
    & $Exe @Arguments -c $PyCheck 2>$null
    return ($LASTEXITCODE -eq 0)
}

# Returns the command (as an array: exe + arguments) that starts a supported Python, or $null
function Find-Python {
    if ($Python) {
        $candidates = , @($Python)
    } else {
        $candidates = @(@('py', '-3.12'), @('py', '-3'), @('python'))
    }
    foreach ($candidate in $candidates) {
        if (Test-Python $candidate[0] @($candidate | Select-Object -Skip 1)) { return , $candidate }
    }
    return $null
}

$pythonCmd = Find-Python
if (-not $pythonCmd) {
    Write-Host 'Python 3.12 or later was not found.' -ForegroundColor Red
    Write-Host 'Install Python 3.12 from https://www.python.org/downloads/windows/ and check "Add python.exe to PATH",'
    Write-Host 'then run this script again. If the Python installer is blocked on your PC, uv (https://docs.astral.sh/uv/)'
    Write-Host 'can install it without one:'
    Write-Host '    uv python install 3.12'
    Write-Host '    powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -Python "$(uv python find 3.12)"'
    exit 1
}
$exe = $pythonCmd[0]
$arguments = @($pythonCmd | Select-Object -Skip 1)
Write-Host "Using $(& $exe @arguments --version)"

# Removed only after a usable Python is found, so a failed run keeps the existing environment
if ($Recreate -and (Test-Path $VenvDir)) {
    Write-Host "Removing $VenvDir"
    Remove-Item -Recurse -Force $VenvDir
}

if ((Test-Path $VenvPython) -and -not (Test-Python $VenvPython @())) {
    Write-Host "The existing $VenvDir uses $(& $VenvPython --version); Python 3.12 or later is required." -ForegroundColor Red
    Write-Host 'Run the script again with -Recreate to rebuild it.'
    exit 1
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment in $VenvDir"
    Invoke-Checked $exe ($arguments + @('-m', 'venv', $VenvDir))
}

Write-Host 'Installing packages from requirements.txt'
Invoke-Checked $VenvPython @('-m', 'pip', 'install', '--upgrade', 'pip')
Invoke-Checked $VenvPython @('-m', 'pip', 'install', '-r', 'requirements.txt')

Write-Host 'Checking the installation'
Invoke-Checked $VenvPython @('-c', 'import xdw_file_playback, PyQt6.QtWidgets')

Write-Host ''
Write-Host 'Setup complete. To start the GUI:' -ForegroundColor Green
Write-Host '    .venv\Scripts\python.exe xdw_file_playback.py'
Write-Host 'or activate the environment first (in PowerShell this may need Set-ExecutionPolicy -Scope CurrentUser RemoteSigned):'
Write-Host '    .venv\Scripts\Activate.ps1'
Write-Host '    python xdw_file_playback.py'
