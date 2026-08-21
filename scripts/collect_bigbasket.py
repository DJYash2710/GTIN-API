"""Phase 2b: scrape BigBasket product pages found from GTIN Google Search.

Requires --confirm. Prefer using already-saved samples/bigbasket/phase2_batch.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.credits import require_apify

load_dotenv(ROOT / ".env")

ACTOR_ID = os.getenv(
    "APIFY_BIGBASKET_ACTOR", "soft_alexist/bigbasket-product-details-scraper"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required. Each product URL is a billed BigBasket actor run.",
    )
    args = parser.parse_args()
    require_apify()
    if not args.confirm:
        raise SystemExit("Refusing to spend Apify credits. Re-run with --confirm.")

    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        raise SystemExit("APIFY_TOKEN is missing in .env")

    summary = json.loads(
        (ROOT / "samples" / "google" / "phase2_summary.json").read_text(encoding="utf-8")
    )
    urls = []
    seen = set()
    for row in summary:
        for url in row.get("bigbasket_urls") or []:
            if "/pd/" in url and url not in seen:
                seen.add(url)
                urls.append(url.split("?")[0])

    print(f"Calling {ACTOR_ID} with {len(urls)} unique BigBasket product URLs.")
    client = ApifyClient(token)
    run = client.actor(ACTOR_ID).call(
        run_input={"urls": urls, "ignore_url_failures": True}
    )
    dataset_id = run.default_dataset_id
    items = list(client.dataset(dataset_id).iterate_items())

    out_dir = ROOT / "samples" / "bigbasket"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "phase2_batch.json"
    out_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Got {len(items)} item(s). Saved {out_path}")
    print(f"Apify dataset: https://console.apify.com/storage/datasets/{dataset_id}")
    if items:
        print("Top-level keys:", sorted(items[0].keys())[:40])


if __name__ == "__main__":
    main()
