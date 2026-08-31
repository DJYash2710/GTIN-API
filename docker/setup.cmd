# @echo off
REM One-command Docker setup for Windows (CMD). Run from anywhere inside the repo.
setlocal
cd /d "%~dp0.."

where docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker is not installed or not on PATH.
  echo Install Docker Desktop: https://www.docker.com/products/docker-desktop/
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop is not running. Open Docker Desktop and wait until it is ready.
  exit /b 1
)

if not exist .env (
  copy /Y .env.example .env >nul
  echo Created .env from .env.example
)

echo.
echo Building and starting MySQL + API (first run may take 3-5 minutes)...
docker compose up --build -d
if errorlevel 1 exit /b 1

echo.
echo Waiting for API...
set /a n=0
:wait
set /a n+=1
curl -sf http://127.0.0.1:8000/health >nul 2>&1
if not errorlevel 1 goto ready
if %n% geq 45 (
  echo API not ready yet. Check logs: docker compose logs api
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait

:ready
echo.
echo ========================================
echo  GTIN API is running
echo ========================================
echo  UI:      http://127.0.0.1:8000/
echo  Health:  http://127.0.0.1:8000/health
echo  API key: dev-local-key  (change API_KEY in .env)
echo  MySQL:   127.0.0.1:3307  user gtin / pass gtin
echo.
echo  LAN:     http://YOUR-IP:8000/  (run ipconfig for IPv4)
echo  Docs:    see DOCKER.md
echo ========================================
endlocal
