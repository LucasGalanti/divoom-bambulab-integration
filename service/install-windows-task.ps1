# Windows Task Scheduler setup script
# Run this in PowerShell (as Administrator) to register the integration as a startup task.
# Edit the paths below to match your environment.

$ProjectPath  = "C:\Projetos_Locais\Divoom_home_bambulab\divoom_bambulab_integration"
$PythonExe    = "$ProjectPath\.venv\Scripts\pythonw.exe"   # pythonw = no console window
$Script       = "$ProjectPath\src\main.py"
$TaskName     = "DivoomBambulab"
$Description  = "BambuLab X1C to Divoom Pixoo 64 integration daemon"

$action  = New-ScheduledTaskAction -Execute $PythonExe -Argument $Script -WorkingDirectory $ProjectPath
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName    $TaskName `
    -Description $Description `
    -Action      $action `
    -Trigger     $trigger `
    -Settings    $settings `
    -RunLevel    Highest `
    -Force

Write-Host "Task '$TaskName' registered. It will start at next logon."
Write-Host "To start immediately: Start-ScheduledTask -TaskName '$TaskName'"
