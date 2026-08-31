"""Load all local samples into MySQL (master catalog + lookup cache).

Does not call Apify. Uses APIFY_ENABLED=false while resolving.
Requires MYSQL_* in .env (set automatically by Docker Compose).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ["APIFY_ENABLED"] = "false"

from app.gtin import is_valid_gtin, normalize_gtin
from app.resolve_samples import resolve_from_samples
from app import store

SAMPLES = ROOT / "samples"
GOOGLE = SAMPLES / "google"


def _gtins() -> list[str]:
    found: set[str] = set()
    listed = json.loads((SAMPLES / "gtins.json").read_text(encoding="utf-8"))
    for row in listed:
        gtin = normalize_gtin(str(row.get("gtin") or ""))
        if is_valid_gtin(gtin):
            found.add(gtin)
    for path in GOOGLE.glob("*.json"):
        stem = path.stem.replace("_mobile", "")
        if stem.isdigit():
            gtin = normalize_gtin(stem)
            if is_valid_gtin(gtin):
                found.add(gtin)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            term = ((item.get("searchQuery") or {}).get("term") or "").strip()
            if not term:
                continue
            first = term.split()[0]
            if first.isdigit():
                gtin = normalize_gtin(first)
                if is_valid_gtin(gtin):
                    found.add(gtin)
    return sorted(found)


def _first(values: list):
    return values[0] if values else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample GTINs into MySQL")
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="Skip seeding when the database already has rows",
    )
    args = parser.parse_args()

    if not store.mysql_configured():
        raise SystemExit("MYSQL_HOST is not set. Sample seed needs MySQL.")
    store.reset_connection()
    if args.if_empty and not store.is_db_empty():
        print("Database already has data; skipping seed.")
        return
    gtins = _gtins()
    print(f"Seeding {len(gtins)} GTINs into {store.backend_name()} ({os.getenv('MYSQL_DATABASE')})")
    saved = 0
    skipped = 0
    empty = 0
    for gtin in gtins:
        resolved = resolve_from_samples(gtin)
        if resolved.get("error"):
            print(f"  skip {gtin}: {resolved.get('error')}")
            skipped += 1
            continue
        store.save_lookup(gtin, resolved)
        name = _first(resolved.get("name") or [])
        price = _first(resolved.get("price") or [])
        weight = _first(resolved.get("weight") or [])
        if not name and not price and not weight:
            print(f"  empty {gtin}: cached lookup only")
            empty += 1
            continue
        store.save_product(
            gtin,
            {"name": name, "price": price, "weight": weight},
            {
                "name": _first(resolved.get("name_source") or []),
                "price": _first(resolved.get("price_source") or []),
                "weight": _first(resolved.get("weight_source") or []),
            },
        )
        saved += 1
        print(f"  ok   {gtin}  {name or '-'}")
    print(f"Done. master_gtin={saved} lookup_only={empty} skipped={skipped}")


if __name__ == "__main__":
    main()
