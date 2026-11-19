# Publishes the backend to a Hugging Face Space (Docker SDK).
# Usage: .\deploy\publish-space.ps1 -SpaceUrl https://huggingface.co/spaces/<user>/<space>
# Auth: use `git credential` / an HF access token with write scope when git asks for a password.
param([Parameter(Mandatory = $true)][string]$SpaceUrl)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$work = Join-Path ([IO.Path]::GetTempPath()) ("dropsafe-space-" + [guid]::NewGuid().ToString("N").Substring(0, 8))

git clone $SpaceUrl $work
if ($LASTEXITCODE) { throw "Could not clone the Space. Create it first (SDK: Docker, blank)." }

# Replace the Space contents with the backend (minus local-only files)
Get-ChildItem $work -Force | Where-Object { $_.Name -ne ".git" } | Remove-Item -Recurse -Force
$excludeDirs = @(".venv", "__pycache__", ".pytest_cache", "data", "tests", "scripts", "logs")
robocopy "$root\backend" $work /E /XD $excludeDirs /XF ".env" ".coverage" "*.log" "*.pyc" "Dockerfile" | Out-Null
Copy-Item "$root\backend\Dockerfile.hosted" "$work\Dockerfile" -Force
Copy-Item "$root\deploy\hf-space\README.md" "$work\README.md" -Force

Push-Location $work
git add -A
git commit -m "Deploy DropSafe backend" 2>&1 | Out-Null
git push
Pop-Location
Remove-Item $work -Recurse -Force
Write-Host "Pushed. The Space will build; watch the Logs tab on Hugging Face."
