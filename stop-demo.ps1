param([switch]$KeepDocker, [switch]$Quiet)
foreach ($port in 8545, 8000, 5173) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
taskkill /F /T /FI "WINDOWTITLE eq DropSafe-Worker*" 2>&1 | Out-Null
taskkill /F /T /FI "WINDOWTITLE eq DropSafe-Tunnel*" 2>&1 | Out-Null
if (-not $KeepDocker) { docker compose stop postgres redis 2>&1 | Out-Null }
if (-not $Quiet) { Write-Host "DropSafe stopped." }
