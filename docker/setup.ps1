# One-command Docker setup for Windows PowerShell
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Test-DockerReady {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: Docker is not installed or not on PATH." -ForegroundColor Red
        Write-Host "Install: https://www.docker.com/products/docker-desktop/"
        exit 1
    }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker Desktop is not running. Open it and wait until Ready." -ForegroundColor Red
        exit 1
    }
}

Test-DockerReady

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

Write-Host ""
Write-Host "Building and starting MySQL + API (first run may take 3-5 minutes)..."
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$port = "8000"
if (Test-Path ".env") {
    $line = Get-Content ".env" | Where-Object { $_ -match '^\s*API_PUBLISH_PORT=' } | Select-Object -First 1
    if ($line -match '=\s*(\d+)') { $port = $Matches[1] }
}

Write-Host ""
Write-Host "Waiting for API on port $port..."
$ready = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    Write-Host "API not ready yet. Check: docker compose logs api" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " GTIN API is running" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host " UI:      http://127.0.0.1:$port/"
Write-Host " Health:  http://127.0.0.1:$port/health"
Write-Host " API key: dev-local-key  (change API_KEY in .env)"
Write-Host " MySQL:   127.0.0.1:3307  user gtin / pass gtin"
Write-Host ""
Write-Host " LAN:     http://<your-ip>:$port/  (ipconfig)"
Write-Host " Docs:    DOCKER.md"
Write-Host "========================================" -ForegroundColor Green
