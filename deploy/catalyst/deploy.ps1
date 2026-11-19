# One-command Catalyst deploy: bundle the backend, inject settings from private files, deploy AppSail.
# Private inputs live OUTSIDE the repository in %USERPROFILE%\.dropsafe\ :
#   neon.json            { "database_url": "postgresql+psycopg://..." }
#   sepolia-wallet.json  { "private_key": "0x..", "contract_address": "0x.." }
#   catalyst-env.json    { "secret_key": "...", "allowed_origins": "https://<pages-domain>" }  (created on first run)
param([switch]$SkipBuild, [string]$AllowedOrigins)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$priv = Join-Path $env:USERPROFILE ".dropsafe"
$neon = Get-Content "$priv\neon.json" -Raw | ConvertFrom-Json
$wallet = Get-Content "$priv\sepolia-wallet.json" -Raw | ConvertFrom-Json
$envFile = "$priv\catalyst-env.json"
if (-not (Test-Path $envFile)) {
    $bytes = New-Object byte[] 48; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $json = @{ secret_key = [Convert]::ToBase64String($bytes); allowed_origins = "https://dropsafe-cns.pages.dev" } | ConvertTo-Json
    [IO.File]::WriteAllText($envFile, $json, (New-Object Text.UTF8Encoding($false)))
}
$cfg = Get-Content $envFile -Raw | ConvertFrom-Json
if ($AllowedOrigins) { $cfg.allowed_origins = $AllowedOrigins; [IO.File]::WriteAllText($envFile, ($cfg | ConvertTo-Json), (New-Object Text.UTF8Encoding($false))) }

if (-not $SkipBuild) { & "$here\build-appsail.ps1" }

$rpc = "https://ethereum-sepolia-rpc.publicnode.com"
$appConfig = [ordered]@{
    command = "sh start-catalyst.sh"
    build_path = "./"
    stack = "python_3_12"
    memory = 512
    scripts = @{}
    env_variables = [ordered]@{
        ENVIRONMENT = "production"; DEBUG = "false"
        SECRET_KEY = $cfg.secret_key
        DATABASE_URL = $neon.database_url
        DATABASE_POOL_SIZE = "3"; DATABASE_MAX_OVERFLOW = "2"
        ALLOWED_ORIGINS = $cfg.allowed_origins
        COOKIE_SECURE = "true"; COOKIE_SAMESITE = "lax"
        STORAGE_BACKEND = "postgres"
        AUDIT_ANCHOR_MODE = "sepolia"; BLOCKCHAIN_NETWORK = "sepolia"
        EVM_RPC_URL = $rpc; BLOCKCHAIN_RPC_URL = $rpc
        ANCHOR_CONTRACT_ADDRESS = $wallet.contract_address
        ANCHOR_SIGNER_PRIVATE_KEY = $wallet.private_key; EVM_SIGNER_PRIVATE_KEY = $wallet.private_key
        SEED_DEMO_DATA = "false"; RUN_MIGRATIONS_ON_START = "false"
    }
}
$appConfig | ConvertTo-Json -Depth 5 | Set-Content "$here\build\app-config.json" -Encoding ascii

Push-Location "$here\project"
npx zcatalyst-cli deploy -ni
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { throw "Catalyst deploy failed (exit $code). See the output above." }
Write-Host "Deployed. Find the service URL in the Catalyst console (AppSail > dropsafe-api)."
