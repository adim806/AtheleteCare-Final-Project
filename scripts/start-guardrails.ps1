$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$service = Join-Path $root "Guardrails-Service"
$venvPython = Join-Path $service ".venv311\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Guardrails venv not found. Run setup in Guardrails-Service (see README.md)."
}

Set-Location $service
& $venvPython -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
