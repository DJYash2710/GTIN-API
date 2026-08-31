# GTIN Product API

Internal lookup: GTIN in, up to 3 names / prices / weights out (each with a matching source list).

A review UI is served at `/`. Lookup a GTIN, pick name / price / weight from up to 3 options, edit any field, then submit. Confirmed values go into the **MySQL** master catalog (`master_gtin` + `source_confidence`). Live/sample lookups are stored in `lookup_cache`.

**Lookup order:** confirmed product → lookup cache → **live Google** (default) → local `samples/` if live is off or fails.

> **Running on another PC?** Use Docker — see **[DOCKER.md](DOCKER.md)** (step-by-step for non-developers).

## Quick start (Docker)

**Windows (easiest):**

```cmd
docker\setup.cmd
```

**PowerShell:**

```powershell
.\docker\setup.ps1
```

Or manually:

```bash
cp .env.example .env   # first time only
docker compose up --build -d
```

That starts **MySQL + API**, creates tables, and seeds sample GTINs on first run. Full details: **[DOCKER.md](DOCKER.md)**.

| Where | URL |
|---|---|
| This PC | `http://127.0.0.1:8000` |
| Other PCs on LAN | `http://<host-ip>:8000` (run `ipconfig` on the host) |

Default ports (override in `.env` if something is already in use):

| Setting | Default | Why |
|---|---|---|
| `API_PUBLISH_PORT` | `8000` | API on your PC |
| `MYSQL_PUBLISH_PORT` | `3307` | Avoids clash with local MySQL on `3306` |
| `API_HOST` | `0.0.0.0` | Listen on all interfaces (LAN access) |

| Service | Credentials |
|---|---|
| MySQL (Workbench from host) | `127.0.0.1:3307`, user `gtin` / password `gtin` / db `gtin` |

**Windows firewall:** if LAN clients cannot connect, allow inbound TCP on port `8000` for Python or Docker.

### Optional `.env` settings

- `APIFY_TOKEN` — required for live Google on cache miss (live search is **on** by default)
- `APIFY_ENABLED=false` — disable live search and use samples only
- `API_PUBLISH_PORT=8080` — if port 8000 is taken
- `MYSQL_PUBLISH_PORT=3308` — if 3307 is taken

MySQL connection settings for the API container are set by Docker Compose; you do not need `MYSQL_HOST` in `.env` for `docker compose up`.

### Make targets

| Command | Description |
|---|---|
| `make up` | Create `.env` if missing, build and start in background |
| `make up-fg` | Same, foreground (see logs) |
| `make down` | Stop containers |
| `make logs` | Follow container logs |
| `make seed` | Re-run sample seed manually |
| `make dev` | Local uvicorn with `--host 0.0.0.0` |
| `make test` | Run pytest locally |
| `make test-docker` | Run pytest inside the API container |
| `make health` | Curl `/health` |

### Example requests

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/products/8901719123870
```

Clear a cached GTIN:

```bash
curl -X DELETE http://127.0.0.1:8000/v1/products/8901719123870/cache
```

## Local development (without Docker)

```bash
python -m venv .venv
.\.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Set `MYSQL_HOST=127.0.0.1` in `.env` if using a local MySQL instance, then:

**Windows (LAN enabled):**

```powershell
.\scripts\run.ps1
```

**Linux / macOS / Git Bash:**

```bash
chmod +x scripts/run.sh
./scripts/run.sh
```

Or manually:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
python scripts/seed_samples_to_db.py
pytest
```

If `MYSQL_HOST` is unset, storage is in-memory (used by tests).

## Tests

```bash
pytest
```

Live lookup searches the GTIN only (desktop, India, 1 page). Price comes from Google's product rich result (`productInfo.price`) and snippet text when that field is empty.
