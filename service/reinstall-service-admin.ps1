# Run this script as Administrator
# Reinstalls the DivoomBambulab NSSM service with the correct Python venv
# Service runs as the current user (not SYSTEM) to access user-local Python install

param(
    [string]$UserName = "lucas_pc\lsnga",
    [string]$UserPassword = ""
)

$root = "C:\Projetos_Locais\Divoom_home_bambulab\divoom_bambulab_integration"
$nssm = "$root\tools\nssm\nssm.exe"
$pythonExe = "$root\.venv\Scripts\python.exe"
$mainScript = "$root\src\main.py"
$logFile = "$root\logs\divoom-bambulab.log"

# Stop and remove old service
Write-Host "Stopping and removing old service..."
& $nssm stop DivoomBambulab 2>&1 | Out-Null
& $nssm remove DivoomBambulab confirm 2>&1 | Out-Null
Start-Sleep -Seconds 2

# Install the service
Write-Host "Installing service..."
& $nssm install DivoomBambulab $pythonExe $mainScript

# Configure service parameters
& $nssm set DivoomBambulab AppDirectory $root
& $nssm set DivoomBambulab AppStdout $logFile
& $nssm set DivoomBambulab AppStderr $logFile
& $nssm set DivoomBambulab AppStdoutCreationDisposition 4
& $nssm set DivoomBambulab AppStderrCreationDisposition 4
& $nssm set DivoomBambulab AppThrottle 0
& $nssm set DivoomBambulab Start SERVICE_AUTO_START
& $nssm set DivoomBambulab DisplayName "Divoom Bambulab Integration"
& $nssm set DivoomBambulab Description "BambuLab X1C to Divoom Pixoo 64 integration"

# Set service to run as user (not SYSTEM) — needed because Python is user-local
if ($UserPassword -ne "") {
    Write-Host "Setting service to run as $UserName ..."
    & $nssm set DivoomBambulab ObjectName $UserName $UserPassword
} else {
    Write-Host ""
    Write-Host "=== ACTION REQUIRED ==="
    Write-Host "The service needs to run as '$UserName' (not SYSTEM)"
    Write-Host "because Python is installed in a user-local directory."
    Write-Host ""
    Write-Host "Run this command (replace YOUR_PASSWORD with your Windows password):"
    Write-Host "  $nssm set DivoomBambulab ObjectName `"$UserName`" `"YOUR_PASSWORD`""
    Write-Host ""
    Write-Host "Then start the service:"
    Write-Host "  $nssm start DivoomBambulab"
    Write-Host "========================"
}

Write-Host ""
Write-Host "Service installed. Run 'nssm start DivoomBambulab' after setting credentials."
