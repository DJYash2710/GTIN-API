#!/usr/bin/env bash
# One-command Docker setup for Linux / macOS / Git Bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is not installed."
  echo "Install: https://docs.docker.com/get-docker/"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running. Start Docker Desktop / docker service."
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

echo ""
echo "Building and starting MySQL + API (first run may take 3-5 minutes)..."
docker compose up --build -d

PORT="${API_PUBLISH_PORT:-8000}"
if [[ -f .env ]]; then
  val=$(grep -E '^\s*API_PUBLISH_PORT=' .env | tail -1 | cut -d= -f2- | tr -d ' \r')
  [[ -n "$val" ]] && PORT="$val"
fi

echo ""
echo "Waiting for API on port ${PORT}..."
for i in $(seq 1 45); do
  if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null; then
    break
  fi
  sleep 2
  if [[ "$i" -eq 45 ]]; then
    echo "API not ready. Check: docker compose logs api"
    exit 1
  fi
done

cat <<EOF

========================================
 GTIN API is running
========================================
 UI:      http://127.0.0.1:${PORT}/
 Health:  http://127.0.0.1:${PORT}/health
 API key: dev-local-key  (change API_KEY in .env)
 MySQL:   127.0.0.1:3307  user gtin / pass gtin

 LAN:     http://<your-ip>:${PORT}/  (ip addr / ifconfig)
 Docs:    DOCKER.md
========================================
EOF
