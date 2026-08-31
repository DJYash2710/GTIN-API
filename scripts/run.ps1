# Run the API locally with venv + LAN access (Windows)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path ".\.venv\Scripts\uvicorn.exe")) {
    Write-Host "Missing .venv — run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$host_bind = if ($env:API_HOST) { $env:API_HOST } else { "0.0.0.0" }
$port = if ($env:API_PORT) { $env:API_PORT } else { "8000" }

Write-Host "Starting API on http://${host_bind}:${port}"
Write-Host "LAN:   http://<this-pc-ip>:${port}/  (find IP: ipconfig)"
Write-Host "Local: http://127.0.0.1:${port}/"

& .\.venv\Scripts\uvicorn.exe app.main:app --reload --host $host_bind --port $port
