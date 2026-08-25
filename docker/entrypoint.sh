#!/bin/sh
# Activate the image virtualenv, then run the CMD (uvicorn by default).
set -e

VENV_PATH="${VENV_PATH:-/opt/venv}"

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
echo "Apify:  APIFY_ENABLED=${APIFY_ENABLED:-false}"

exec "$@"
