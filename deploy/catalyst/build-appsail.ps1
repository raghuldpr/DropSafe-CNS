# Builds the Zoho Catalyst AppSail source folder (no Docker needed).
# Output: deploy/catalyst/build/  (backend code + Linux/Python 3.12 wheels in ./packages)
param([string]$PythonVersion = "3.12")
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$out = Join-Path $PSScriptRoot "build"
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
$abi = "cp" + ($PythonVersion -replace "\.", "")

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory $out | Out-Null

# 1. application source (no venv, tests, local data, secrets)
robocopy "$root\backend" $out /E /XD .venv __pycache__ .pytest_cache data tests scripts logs packages `
    /XF .env .env.* .coverage "*.log" "*.pyc" Dockerfile* requirements.txt | Out-Null
Copy-Item "$root\backend\requirements-hosted.txt" "$out\requirements.txt" -Force

# 2. Linux wheels for the Catalyst runtime, downloaded from this PC.
#    Pin the exact versions of the tested virtualenv (minus Windows-only and test-only packages)
#    and install them without dependency solving, so Windows-only markers (pywin32) never apply.
$skip = '^(aiosqlite|coverage|iniconfig|pluggy|pytest.*|pywin32.*|colorama|Pygments)=='
$lock = Join-Path $out "requirements.lock.txt"
& $py -m pip freeze 2>$null | Where-Object { $_ -notmatch $skip } | Set-Content $lock -Encoding ascii
& $py -m pip install --quiet --upgrade --no-deps --target "$out\packages" `
    --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 `
    --python-version $PythonVersion --implementation cp --abi $abi --only-binary=:all: `
    --default-timeout 120 --retries 10 -r $lock
if ($LASTEXITCODE) { throw "pip failed (a package may lack a Linux wheel for Python $PythonVersion)" }

# 3. drop bytecode and test folders from the bundle to keep it small
Get-ChildItem "$out\packages" -Recurse -Directory -Include __pycache__, tests, test | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
$mb = [math]::Round((Get-ChildItem $out -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "Bundle ready: $out ($mb MB)"
