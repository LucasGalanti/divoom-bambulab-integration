# ============================================================================
# uninstall-windows-service.ps1
#
# Stops and removes the DivoomBambulab Windows service installed by
# install-windows-service.ps1.  NSSM and log files are left in place.
#
# Usage:
#   Right-click → "Run with PowerShell"   (will self-elevate)
#   — or —
#   powershell -ExecutionPolicy Bypass -File service\uninstall-windows-service.ps1
# ============================================================================

#Requires -Version 5.1

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$ErrorActionPreference = "Stop"
$ServiceName = "DivoomBambulab"
$NssmDir     = "$PSScriptRoot\..\tools\nssm"
$NssmExe     = if (Get-Command nssm -ErrorAction SilentlyContinue) { "nssm" } else { "$NssmDir\nssm.exe" }

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Host "Service '$ServiceName' not found — nothing to remove." -ForegroundColor Yellow
    exit 0
}

Write-Host "Stopping '$ServiceName'..." -ForegroundColor Cyan
& $NssmExe stop $ServiceName confirm 2>$null

Write-Host "Removing '$ServiceName'..." -ForegroundColor Cyan
& $NssmExe remove $ServiceName confirm

Write-Host "Service removed." -ForegroundColor Green
