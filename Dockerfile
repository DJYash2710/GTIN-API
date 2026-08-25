# GTIN Product API
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VENV_PATH=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# System deps (certs for HTTPS / Apify; build tools only if wheels need them)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Isolated virtualenv (same idea as local .venv)
RUN python -m venv "$VENV_PATH" \
    && "$VENV_PATH/bin/pip" install --upgrade pip setuptools wheel

COPY requirements.txt .
RUN "$VENV_PATH/bin/pip" install -r requirements.txt

COPY app ./app
COPY samples ./samples
COPY scripts ./scripts
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Defaults; compose / .env override these at runtime
ENV APIFY_ENABLED=false \
    API_KEY=dev-local-key \
    MYSQL_HOST=mysql \
    MYSQL_PORT=3306 \
    MYSQL_USER=gtin \
    MYSQL_PASSWORD=gtin \
    MYSQL_DATABASE=gtin \
    NAME_TTL_DAYS=30 \
    PRICE_TTL_HOURS=12

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
