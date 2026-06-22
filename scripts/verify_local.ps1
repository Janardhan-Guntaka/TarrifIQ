# Smoke test local TariffIQ stack (run from repo root after .env + ingest)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "=== TariffIQ local verify ===" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Write-Host "Missing .env — copy from .env.example and fill secrets." -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/3] Python imports..." -ForegroundColor Yellow
python -c "from backend.api.main import app; print('OK:', app.title)"

Write-Host "`n[2/3] Health (start API in another terminal: python run.py api)..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    $health | ConvertTo-Json -Depth 5
} catch {
    Write-Host "API not running on :8000 — run: python run.py api" -ForegroundColor Red
}

Write-Host "`n[3/3] Classify sample..." -ForegroundColor Yellow
try {
    $body = @{ query = "gaming laptop from China"; country = "China"; customs_value = 1200 } | ConvertTo-Json
    $result = Invoke-RestMethod -Uri "http://localhost:8000/v1/classify" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 120
    Write-Host "HTS:" $result.classification.hts_code "Duty:" $result.duty.total_rate
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host "`nDone." -ForegroundColor Green
