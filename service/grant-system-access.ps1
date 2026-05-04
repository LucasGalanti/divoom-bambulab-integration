# Run this script as Administrator
# Grants SYSTEM account read+execute access to user-local Python install
# so the NSSM service (running as SYSTEM) can find the Python interpreter

$pythonBase = "C:\Users\lsnga\AppData\Local\Python"
$root = "C:\Projetos_Locais\Divoom_home_bambulab\divoom_bambulab_integration"

Write-Host "Granting SYSTEM access to Python install..."
icacls $pythonBase /grant "NT AUTHORITY\SYSTEM:(OI)(CI)RX" /T /Q
Write-Host "SYSTEM access granted to $pythonBase"

# Also ensure logs dir and .env are accessible
Write-Host "Granting SYSTEM access to project logs and .env..."
icacls "$root\logs" /grant "NT AUTHORITY\SYSTEM:(OI)(CI)F" /T /Q
if (Test-Path "$root\.env") {
    icacls "$root\.env" /grant "NT AUTHORITY\SYSTEM:R" /Q
}
Write-Host "Done."
