#!/usr/bin/env bash
# Run the API locally with venv + LAN access (Linux / macOS / Git Bash)
set -euo pipefail
cd "$(dirname "$0")/.."

API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "Missing .venv — run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "Starting API on http://${API_HOST}:${API_PORT}"
echo "LAN:   http://<this-pc-ip>:${API_PORT}/"
echo "Local: http://127.0.0.1:${API_PORT}/"

exec .venv/bin/uvicorn app.main:app --reload --host "$API_HOST" --port "$API_PORT"
