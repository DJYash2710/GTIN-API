"""One desktop Google Search in India. Default: a single GTIN, one page.

Do not add site:/inurl: queries here — each extra line is another billed search page.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.apify_google import google_run_input
from app.credits import require_apify

load_dotenv(ROOT / ".env")

TEST_GTIN = "8901719123870"
ACTOR_ID = os.getenv("APIFY_GOOGLE_ACTOR_ID") or os.getenv(
    "APIFY_GOOGLE_ACTOR", "nFJndFXA5zjCTuudP"
)


def main() -> None:
    require_apify()
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        raise SystemExit("APIFY_TOKEN is missing in .env")

    print(f"Calling actor {ACTOR_ID}")
    print(f"Query: {TEST_GTIN} (desktop, India, 1 page)")

    client = ApifyClient(token)
    run = client.actor(ACTOR_ID).call(run_input=google_run_input(TEST_GTIN))
    dataset_id = run.default_dataset_id
    items = list(client.dataset(dataset_id).iterate_items())

    out_dir = ROOT / "samples" / "google"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{TEST_GTIN}_mobile.json"
    out_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Saved {len(items)} dataset item(s) to {out_path}")
    for item in items:
        device = (item.get("searchQuery") or {}).get("device")
        term = (item.get("searchQuery") or {}).get("term")
        organic = item.get("organicResults") or []
        print(f"{term} device={device}: {len(organic)} organic result(s)")
        for result in organic[:5]:
            print(f"  - {result.get('title')}")
            print(f"    {result.get('url')}")


if __name__ == "__main__":
    main()
