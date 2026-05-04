# ===========================================================================
# install-windows-service.ps1
#
# Installs the Divoom BambuLab integration as a Windows Service using NSSM
# (Non-Sucking Service Manager). The service starts at boot, runs silently
# in the background, and auto-restarts on failure - no terminal needed.
#
# Requirements:
#   - Run this script as Administrator
#   - Python installed (for all users preferred, or user-local with SYSTEM ACL granted)
#   - Dependencies installed: pip install paho-mqtt Pillow requests pyyaml python-dotenv
#   - .env file filled in with your credentials
#
# NSSM will be downloaded automatically to the project folder if not found
# on PATH. No system-wide installation required.
#
# Usage:
#   Right-click this file -> "Run with PowerShell"   (will self-elevate)
#   -- or --
#   powershell -ExecutionPolicy Bypass -File service\install-windows-service.ps1
# ===========================================================================

#Requires -Version 5.1

# Self-elevate if not already running as Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Configuration - edit if your project lives somewhere else
# ---------------------------------------------------------------------------
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe   = "C:\Users\lsnga\AppData\Local\Python\bin\python.exe"
$Script      = "$ProjectRoot\src\main.py"
$ServiceName = "DivoomBambulab"
$DisplayName = "Divoom BambuLab Integration"
$Description = "Displays BambuLab X1C print progress on a Divoom Pixoo 64 in real time."
$NssmDir     = "$ProjectRoot\tools\nssm"
$NssmExe     = "$NssmDir\nssm.exe"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step {
    param([string]$msg)
    Write-Host ""
    Write-Host ">>> $msg" -ForegroundColor Cyan
}

function Write-OK {
    param([string]$msg)
    Write-Host "    OK: $msg" -ForegroundColor Green
}

function Write-Fail {
    param([string]$msg)
    Write-Host "    ERROR: $msg" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Step 1 - Validate project files
# ---------------------------------------------------------------------------
Write-Step "Validating project files"

if (-not (Test-Path $PythonExe)) {
    Write-Fail "python.exe not found at $PythonExe -- Install Python and run: pip install paho-mqtt Pillow requests pyyaml python-dotenv"
}
if (-not (Test-Path $Script)) {
    Write-Fail "main.py not found at $Script"
}
if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Fail ".env not found. Copy .env.example to .env and fill in your credentials."
}

Write-OK "All project files present"

# ---------------------------------------------------------------------------
# Step 2 - Get NSSM
# ---------------------------------------------------------------------------
Write-Step "Locating NSSM"

$NssmCmd = Get-Command nssm -ErrorAction SilentlyContinue
if ($NssmCmd) {
    $NssmExe = $NssmCmd.Source
    Write-OK "Found NSSM on PATH: $NssmExe"
} elseif (Test-Path $NssmExe) {
    Write-OK "Found bundled NSSM: $NssmExe"
} else {
    Write-Host "    NSSM not found - downloading to $NssmDir ..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $NssmDir | Out-Null

    $ZipPath = "$env:TEMP\nssm.zip"
    $NssmUrl = "https://nssm.cc/release/nssm-2.24.zip"

    try {
        Invoke-WebRequest -Uri $NssmUrl -OutFile $ZipPath -UseBasicParsing
    } catch {
        Write-Fail "Download failed. Download manually from https://nssm.cc and place nssm.exe in $NssmDir"
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    $entry = $zip.Entries | Where-Object { $_.FullName -like "*/win64/nssm.exe" } | Select-Object -First 1
    if (-not $entry) {
        $zip.Dispose()
        Write-Fail "Could not find nssm.exe in the downloaded zip."
    }
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $NssmExe, $true)
    $zip.Dispose()
    Remove-Item $ZipPath -Force

    Write-OK "NSSM downloaded to $NssmExe"
}

# ---------------------------------------------------------------------------
# Step 3 - Remove existing service if present
# ---------------------------------------------------------------------------
Write-Step "Checking for existing service"

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "    Existing service found - stopping and removing..." -ForegroundColor Yellow
    & $NssmExe stop $ServiceName confirm 2>&1 | Out-Null
    & $NssmExe remove $ServiceName confirm
    Write-OK "Old service removed"
} else {
    Write-OK "No existing service found"
}

# ---------------------------------------------------------------------------
# Step 4 - Install the service
# ---------------------------------------------------------------------------
Write-Step "Installing Windows service"

& $NssmExe install $ServiceName $PythonExe $Script
if ($LASTEXITCODE -ne 0) {
    Write-Fail "NSSM install failed (exit $LASTEXITCODE)"
}

& $NssmExe set $ServiceName AppDirectory $ProjectRoot
& $NssmExe set $ServiceName DisplayName $DisplayName
& $NssmExe set $ServiceName Description $Description
& $NssmExe set $ServiceName AppExit Default Restart
& $NssmExe set $ServiceName AppRestartDelay 10000

$LogDir = "$ProjectRoot\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
& $NssmExe set $ServiceName AppStdout "$LogDir\divoom-bambulab.log"
& $NssmExe set $ServiceName AppStderr "$LogDir\divoom-bambulab.log"
& $NssmExe set $ServiceName AppRotateFiles 1
& $NssmExe set $ServiceName AppRotateBytes 5242880
& $NssmExe set $ServiceName Start SERVICE_AUTO_START

Write-OK "Service installed"

# ---------------------------------------------------------------------------
# Step 5 - Start the service now
# ---------------------------------------------------------------------------
Write-Step "Starting service"

& $NssmExe start $ServiceName
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Service failed to start. Check logs at $LogDir\divoom-bambulab.log"
}

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
Write-OK "Service status: $($svc.Status)"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Service installed and running!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Manage via:   services.msc  (search '$DisplayName')"
Write-Host "  Live logs:    $LogDir\divoom-bambulab.log"
Write-Host "  Stop:         nssm stop $ServiceName"
Write-Host "  Restart:      nssm restart $ServiceName"
Write-Host "  Uninstall:    service\uninstall-windows-service.ps1"
Write-Host ""