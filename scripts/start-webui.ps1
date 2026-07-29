$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$service = Join-Path $root "WebUI-Service"

if (-not (Test-Path (Join-Path $service "package.json"))) {
    Write-Error "WebUI-Service not found."
}

Set-Location $service

if (-not (Test-Path (Join-Path $service "node_modules"))) {
    Write-Host "Installing npm dependencies..."
    npm install
}

if (-not (Test-Path (Join-Path $service ".env"))) {
    Copy-Item (Join-Path $service ".env.example") (Join-Path $service ".env")
    Write-Host "Created .env from .env.example — set N8N_WEBHOOK_URL before submitting reports."
}

npm run dev
