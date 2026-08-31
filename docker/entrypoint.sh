#!/bin/sh
# Activate the image virtualenv, wait for MySQL, seed on first run, then start the API.
set -e

VENV_PATH="${VENV_PATH:-/opt/venv}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"

if [ ! -x "$VENV_PATH/bin/python" ]; then
  echo "ERROR: virtualenv not found at $VENV_PATH" >&2
  exit 1
fi

# shellcheck disable=SC1091
. "$VENV_PATH/bin/activate"

echo "Python: $(python --version)"
echo "Venv:   $VENV_PATH"
echo "CWD:    $(pwd)"
echo "MySQL:  ${MYSQL_HOST:-unset}:${MYSQL_PORT:-3306}/${MYSQL_DATABASE:-unset}"
echo "Apify:  APIFY_ENABLED=${APIFY_ENABLED:-true}"
echo "Listen: ${API_HOST}:${API_PORT} (LAN: use this PC's IP instead of 127.0.0.1)"

python - <<'PY'
import os
import sys
import time

import pymysql

host = os.getenv("MYSQL_HOST", "mysql")
port = int(os.getenv("MYSQL_PORT", "3306"))
user = os.getenv("MYSQL_USER", "gtin")
password = os.getenv("MYSQL_PASSWORD", "gtin")
database = os.getenv("MYSQL_DATABASE", "gtin")

for attempt in range(1, 61):
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=3,
        )
        conn.close()
        print(f"MySQL ready ({host}:{port}/{database})")
        break
    except Exception as exc:
        if attempt == 60:
            print(f"ERROR: MySQL not ready after 60s: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        time.sleep(1)
PY

python scripts/seed_samples_to_db.py --if-empty

exec "$@"
