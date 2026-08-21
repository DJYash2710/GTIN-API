# GTIN Product API

Internal lookup: GTIN in, up to 3 names / prices / weights out (each with a matching source list). No description.

A basic review UI is served at `/`. Lookup a GTIN, click name / price / weight for up to 3 options, edit any field, then submit. Confirmed values go into the **MySQL** master catalog (`products` + `source_confidence`). Live/sample lookups are stored in `lookup_cache`.

GET lookup order: **cache first** (confirmed product, then lookup cache), then **live Google** on miss or stale price (`APIFY_ENABLED=true`). If live search is off, it falls back to `samples/`. Successful lookups are written back to cache. `force_refresh=true` skips cache and searches live.

TTLs (independent): name/weight **30 days**, price **12 hours**. `DELETE /v1/products/{gtin}/cache` invalidates both the lookup cache and the confirmed row.

If `MYSQL_HOST` is unset, storage is in-memory (used by tests).

## Setup

```
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the API

```
uvicorn app.main:app --reload --port 8000
```

```
curl -H "Authorization: Bearer dev-local-key" http://127.0.0.1:8000/health
curl -H "Authorization: Bearer dev-local-key" http://127.0.0.1:8000/v1/products/8901719123870
```

Open `http://127.0.0.1:8000/` for the review form.

Live Google (cache miss, stale price, or `force_refresh=true` — spends credits, one search page):

```
curl -H "Authorization: Bearer dev-local-key" "http://127.0.0.1:8000/v1/products/8901719123870?force_refresh=true"
curl -X DELETE -H "Authorization: Bearer dev-local-key" http://127.0.0.1:8000/v1/products/8901719123870/cache
```

Or `docker compose up --build` (API + MySQL).

Set MySQL in `.env` for a local uvicorn process:

```
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=gtin
MYSQL_PASSWORD=gtin
MYSQL_DATABASE=gtin
```

## Tests

```
pytest
```

Live lookup searches the GTIN only (desktop, India, 1 page). It does **not** add `site:` / `inurl:` filters and does **not** scrape BigBasket or Flipkart product pages. Price comes from Google's product rich result (`productInfo.price`, e.g. ₹47.00) and from snippet text when that field is empty.

Host priority: BigBasket → JioMart → Amazon.in → Flipkart → Starquik → Open Food Facts, then other snippets that mention the GTIN. Each of `name`, `price`, and `weight` is its own list (max 3), ranked by source confidence, with a parallel `*_source` list.

Batch collect scripts still need `APIFY_ENABLED=true` **and** `--confirm`.
