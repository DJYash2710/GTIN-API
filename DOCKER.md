# GTIN Product API — Docker guide

Run the **full stack** (MySQL + API + sample data) on any PC with **Docker Desktop only**.  
No Python, venv, or local MySQL install required.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| **Docker Desktop** | [Download for Windows](https://www.docker.com/products/docker-desktop/) |
| **8 GB RAM** (recommended) | Docker + MySQL + API |
| **Ports free** | `8000` (API), `3307` (MySQL on your PC) — changeable in `.env` |

After installing Docker Desktop:

1. Open **Docker Desktop**
2. Wait until status is **Running** (whale icon steady, not starting)
3. Open a **new** terminal (PowerShell or CMD)

Check:

```powershell
docker --version
docker compose version
```

If `docker` is not found, restart the terminal or reboot once after install.

---

## 2. Get the project

**Option A — Git**

```powershell
git clone <repo-url>
cd "GTIN API"
```

**Option B — Zip**

Unzip the folder. Do **not** include someone else's `.venv` or `.env` (secrets).

You need at minimum:

- `app/`, `samples/`, `scripts/`, `docker/`
- `Dockerfile`, `docker-compose.yml`, `.env.example`, `requirements.txt`

---

## 3. Start everything (pick one)

### Windows — double-click or CMD

```cmd
docker\setup.cmd
```

### Windows — PowerShell

```powershell
.\docker\setup.ps1
```

### Linux / macOS / Git Bash

```bash
chmod +x docker/setup.sh
./docker/setup.sh
```

### Manual (all platforms)

```powershell
copy .env.example .env
docker compose up --build -d
```

**First run** builds the image and downloads MySQL (~3–5 minutes). Later starts are faster.

---

## 4. Verify it works

| What | URL / command |
|---|---|
| **Review UI** | http://127.0.0.1:8000/ |
| **Health** | http://127.0.0.1:8000/health |
| **Sample GTIN** | Lookup `8901719123870` (Parle-G) in the UI |
| **API key** (UI field) | `dev-local-key` unless you changed `API_KEY` in `.env` |

Command line:

```powershell
curl http://127.0.0.1:8000/health
curl -H "Authorization: Bearer dev-local-key" http://127.0.0.1:8000/v1/products/8901719123870
```

Expected: `"cache": "hit"` or `"sample"` and product name/price/weight.

Container status:

```powershell
docker compose ps
```

Both `gtin-api` and `gtin-mysql` should be **healthy** or **running**.

---

## 5. What Docker starts for you

| Container | Role |
|---|---|
| **gtin-mysql** | MySQL 8.4, database `gtin`, user `gtin` / password `gtin` |
| **gtin-api** | FastAPI on `0.0.0.0:8000`, Python venv inside image |

**On first API start (automatic):**

1. Waits for MySQL
2. Creates tables: `master_gtin`, `lookup_cache`, `source_confidence`
3. Seeds ~24 sample GTINs from `samples/` (skipped if DB already has data)

Data persists in Docker volume `mysql_data` until you run `docker compose down -v`.

---

## 6. Live Google search (Apify) — default ON

On cache miss, the API calls **Google Search via Apify** automatically.

1. Add your token to `.env`:
   ```
   APIFY_TOKEN=your_apify_token_here
   ```
   (`APIFY_ENABLED=true` is already the default.)

2. Restart API if it was already running:
   ```powershell
   docker compose restart api
   ```

To **disable** live search and use local samples only:

```
APIFY_ENABLED=false
```

Without a valid `APIFY_TOKEN`, cache misses may return **503** instead of live results.

---

## 7. Access from other PCs (same Wi‑Fi / LAN)

On the **host PC**:

```powershell
ipconfig
```

Note **IPv4 Address** (e.g. `192.168.1.50`).

On another PC browser:

```
http://192.168.1.50:8000/
```

If it does not load, allow **inbound TCP port 8000** in Windows Firewall on the host.

---

## 8. MySQL from Workbench (optional)

Connect from the host machine (not from inside Docker):

| Field | Value |
|---|---|
| Host | `127.0.0.1` |
| Port | `3307` (not 3306 — avoids clash with local MySQL) |
| User | `gtin` |
| Password | `gtin` |
| Database | `gtin` |

Tables: `master_gtin`, `lookup_cache`, `source_confidence`

---

## 9. Useful commands

```powershell
# Follow logs
docker compose logs -f

# API logs only
docker compose logs -f api

# Stop (keep data)
docker compose down

# Stop and delete DB data
docker compose down -v

# Rebuild after code update
docker compose up --build -d

# Re-seed samples manually
docker compose exec api python scripts/seed_samples_to_db.py

# Shell inside API container
docker compose exec api sh

# Run tests inside container
docker compose exec api python -m pytest tests/ -q
```

---

## 10. Change ports (if something is already in use)

Edit `.env` **before** `docker compose up`:

```env
API_PUBLISH_PORT=8080
MYSQL_PUBLISH_PORT=3308
```

Then:

```powershell
docker compose down
docker compose up --build -d
```

Open UI at http://127.0.0.1:8080/

---

## 11. Troubleshooting

| Problem | What to do |
|---|---|
| `docker` not recognized | Install Docker Desktop; open **new** terminal |
| Docker not running | Open Docker Desktop; wait for Ready |
| Port 8000 in use | Set `API_PUBLISH_PORT=8080` in `.env`, restart compose |
| Port 3307 in use | Set `MYSQL_PUBLISH_PORT=3308` in `.env` |
| `read-only file system` | Restart Docker Desktop |
| API unhealthy | `docker compose logs api` — often MySQL still starting; wait 1 min |
| Empty UI / 401 | Use API key `dev-local-key` or your `API_KEY` from `.env` |
| Live search 503 | Add valid `APIFY_TOKEN` to `.env`, or set `APIFY_ENABLED=false` for samples only |
| WSL / virtualization error | Enable virtualization in BIOS; use WSL2 backend in Docker settings |

---

## 12. Stop / uninstall

```powershell
docker compose down -v
```

Remove project folder. Optionally uninstall Docker Desktop from Windows Settings.

---

## Quick reference

```
Setup:     docker\setup.cmd   (Windows)  or  ./docker/setup.sh
UI:        http://127.0.0.1:8000/
API key:   dev-local-key
Sample:    GTIN 8901719123870
MySQL:     127.0.0.1:3307  gtin / gtin
```

For development without Docker, see the main [README.md](README.md).
