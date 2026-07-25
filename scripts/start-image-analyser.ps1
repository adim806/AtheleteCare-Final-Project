$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$service = Join-Path $root "Image-Analyser-Service"
$venvPython = Join-Path $service ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Image Analyser venv not found. Run setup in Image-Analyser-Service (see README.md)."
}

Set-Location $service
& $venvPython -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
