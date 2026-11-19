# DropSafe one-command demo launcher.  Usage:  .\start-demo.ps1 [-Keep]
#   Default : clean slate every start (fresh DB + fresh chain + reseeded demo users), because
#             the local chain and file storage are in-memory and reset on restart.
#   -Keep   : keep the existing database (stale batches will fail on-chain verification)
#   -Public : also share the demo on a public https URL via a free Cloudflare quick tunnel
#             (needs `cloudflared`: winget install Cloudflare.cloudflared)
param([switch]$Keep, [switch]$Reset, [switch]$Public)
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
Set-Location $root
$py = "$root\backend\.venv\Scripts\python.exe"

function Wait-Url($url, $name, $secs = 60) {
    for ($i = 0; $i -lt $secs; $i++) {
        try { Invoke-RestMethod $url -TimeoutSec 2 | Out-Null; Write-Host "  [ok] $name"; return } catch { Start-Sleep 1 }
    }
    throw "$name did not come up ($url)"
}

Write-Host "1/5 Docker (Postgres + Redis)"
docker info *> $null; if ($LASTEXITCODE) { throw "Docker Desktop is not running." }
if (-not $Keep) { docker compose down -v 2>&1 | Out-Null }
docker compose up -d --wait postgres redis 2>&1 | Out-Null

Write-Host "2/5 Local blockchain"
& "$root\stop-demo.ps1" -KeepDocker -Quiet
$bc = Start-Process cmd -ArgumentList "/c npx hardhat node > ..\hardhat.log 2>&1" -WorkingDirectory "$root\blockchain" -WindowStyle Minimized -PassThru
$body = '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'
for ($i=0; $i -lt 60; $i++) { try { Invoke-RestMethod http://127.0.0.1:8545 -Method Post -ContentType application/json -Body $body -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep 1 } }
Push-Location "$root\blockchain"
$out = npx hardhat run scripts/deploy.ts --network localhost 2>&1 | Out-String
Pop-Location
$addr = [regex]::Match($out, "deployed to: (0x[0-9a-fA-F]{40})").Groups[1].Value
if (-not $addr) { throw "Contract deploy failed:`n$out" }
Write-Host "  [ok] AuditAnchor at $addr"
foreach ($f in "$root\backend\.env", "$root\.env") {
    if (Test-Path $f) { (Get-Content $f) -replace '^ANCHOR_CONTRACT_ADDRESS=.*', "ANCHOR_CONTRACT_ADDRESS=`"$addr`"" | Set-Content $f }
}

Write-Host "3/5 Database migrate + seed"
Push-Location "$root\backend"
& $py -m alembic upgrade head 2>&1 | Out-Null
& $py seed.py 2>&1 | Out-Null
Pop-Location

Write-Host "4/5 Backend (FastAPI :8000)"
Start-Process cmd -ArgumentList "/c `"$py`" run.py > ..\backend.log 2>&1" -WorkingDirectory "$root\backend" -WindowStyle Minimized
Wait-Url "http://127.0.0.1:8000/api/v1/health" "backend"

Write-Host "    Audit anchoring worker"
Start-Process cmd -ArgumentList "/c title DropSafe-Worker & `"$py`" -m app.worker.worker > ..\worker.log 2>&1" -WorkingDirectory "$root\backend" -WindowStyle Minimized

Write-Host "5/5 Frontend (Vite :5173)"
if ($Public) { $env:VITE_BLOCKCHAIN_RPC_URL = "/rpc" }
Start-Process cmd -ArgumentList "/c npm run dev > ..\frontend.log 2>&1" -WorkingDirectory "$root\frontend" -WindowStyle Minimized
Wait-Url "http://localhost:5173/api/v1/health" "frontend (+proxy)"

Write-Host "`nDropSafe is live: http://localhost:5173"
Write-Host "Demo logins: alice@dropsafe.local / AlicePass123!   bob@dropsafe.local / BobPass123!"
Write-Host "             charlie@dropsafe.local / CharliePass123!   admin@dropsafe.local / AdminPass123!"
Write-Host "Stop with: .\stop-demo.ps1"
if ($Public) {
    if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
        Write-Host "`n-Public needs cloudflared. Install: winget install Cloudflare.cloudflared (then rerun)." -ForegroundColor Yellow
    } else {
        Write-Host "`nStarting public tunnel (URL appears below, also saved in tunnel.log)..."
        Start-Process cmd -ArgumentList "/c title DropSafe-Tunnel & cloudflared tunnel --url http://localhost:5173 > tunnel.log 2>&1" -WorkingDirectory $root -WindowStyle Minimized
        $url = $null
        for ($i = 0; $i -lt 30 -and -not $url; $i++) {
            Start-Sleep 1
            $log = Join-Path $root "tunnel.log"
            if (Test-Path $log) { $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1; if ($m) { $url = $m.Matches[0].Value } }
        }
        if ($url) { Write-Host "PUBLIC URL: $url" -ForegroundColor Green } else { Write-Host "Tunnel URL not found yet; check tunnel.log" -ForegroundColor Yellow }
    }
}
Start-Process "http://localhost:5173"
