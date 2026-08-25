# GTIN Product API

Internal lookup: GTIN in, up to 3 names / prices / weights out (each with a matching source list). No description.

A basic review UI is served at `/`. Lookup a GTIN, click name / price / weight for up to 3 options, edit any field, then submit. Confirmed values go into the **MySQL** master catalog (`master_gtin` + `source_confidence`). Live/sample lookups are stored in `lookup_cache`.

**One lookup URL:** `GET /v1/products/{gtin}` — **cache first** (confirmed product, then lookup cache), then **live Google** on miss or stale price (`APIFY_ENABLED=true`). If live search is off, it falls back to `samples/`. Successful lookups are written back to cache.

TTLs (independent): name/weight **30 days**, price **12 hours**. `DELETE /v1/products/{gtin}/cache` invalidates both the lookup cache and the confirmed row.

If `MYSQL_HOST` is unset, storage is in-memory (used by tests).

## Setup (local)

```
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Docker (recommended)

Builds a Python 3.12 image with its own virtualenv at `/opt/venv`, installs `requirements.txt`, activates the venv, and runs uvicorn. MySQL starts beside the API.

```
docker compose up --build
```

Then:

```
curl http://127.0.0.1:8000/health
curl -H "Authorization: Bearer dev-local-key" http://127.0.0.1:8000/v1/products/8901719123870
```

Open `http://127.0.0.1:8000/` for the review form.

| Service | URL / host | Credentials |
|---|---|---|
| API | `http://127.0.0.1:8000` | Bearer `API_KEY` (default `dev-local-key`) |
| MySQL (from host) | `127.0.0.1:3306` | user `gtin` / password `gtin` / db `gtin` |
| MySQL (from API container) | host `mysql` | same |

`.env` is loaded for secrets (`APIFY_TOKEN`, `APIFY_ENABLED`, …). Compose **overrides** `MYSQL_HOST` to `mysql` so the API talks to the MySQL container (ignore `127.0.0.1` from a local Workbench `.env`).

Seed sample JSON into the Docker MySQL:

```
docker compose exec api python scripts/seed_samples_to_db.py
```

Stop:

```
docker compose down
```

## Run the API (local uvicorn)

```
uvicorn app.main:app --reload --port 8000
```

```
curl -H "Authorization: Bearer dev-local-key" http://127.0.0.1:8000/health
curl -H "Authorization: Bearer dev-local-key" http://127.0.0.1:8000/v1/products/8901719123870
```

Open `http://127.0.0.1:8000/` for the review form.

On cache miss (or stale price) with `APIFY_ENABLED=true`, that same GET spends Apify credits (one Google Search page). To clear a bad row:

```
curl -X DELETE -H "Authorization: Bearer dev-local-key" http://127.0.0.1:8000/v1/products/8901719123870/cache
```

Set MySQL in `.env` for a local uvicorn process (Workbench / local MySQL):

```
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=gtin
```

## Tests

```
pytest
```

Live lookup searches the GTIN only (desktop, India, 1 page). It does **not** add `site:` / `inurl:` filters and does **not** scrape BigBasket or Flipkart product pages. Price comes from Google's product rich result (`productInfo.price`, e.g. ₹47.00) and from snippet text when that field is empty.

Host priority: BigBasket → JioMart → Amazon.in → Flipkart → Starquik → Open Food Facts, then other snippets that mention the GTIN. Each of `name`, `price`, and `weight` is its own list (max 3), ranked by source confidence, with a parallel `*_source` list.

Batch collect scripts still need `APIFY_ENABLED=true` **and** `--confirm`.
