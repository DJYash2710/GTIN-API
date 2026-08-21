"""Phase 2: Google Search each GTIN (barcode only) and save SERP JSON.

Desktop + India. Each GTIN is one billed search page — requires --confirm.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from apify_client import ApifyClient
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.apify_google import google_run_input
from app.credits import require_apify

load_dotenv(ROOT / ".env")

ACTOR_ID = os.getenv("APIFY_GOOGLE_ACTOR_ID") or os.getenv(
    "APIFY_GOOGLE_ACTOR", "nFJndFXA5zjCTuudP"
)


def retailer_from_url(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if "bigbasket.com" in host:
        return "bigbasket"
    if "flipkart.com" in host:
        return "flipkart"
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required. Batch search spends one Google page per GTIN.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap how many GTINs to search.")
    args = parser.parse_args()
    require_apify()
    if not args.confirm:
        raise SystemExit(
            "Refusing to spend Apify credits. Re-run with --confirm [--limit N]."
        )

    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        raise SystemExit("APIFY_TOKEN is missing in .env")

    gtins = json.loads((ROOT / "samples" / "gtins.json").read_text(encoding="utf-8"))
    if args.limit is not None:
        gtins = gtins[: args.limit]
    queries = "\n".join(item["gtin"] for item in gtins)
    print(f"Calling {ACTOR_ID} with {len(gtins)} GTIN queries (desktop, India, 1 page each).")

    client = ApifyClient(token)
    run = client.actor(ACTOR_ID).call(run_input=google_run_input(queries))
    dataset_id = run.default_dataset_id
    items = list(client.dataset(dataset_id).iterate_items())

    out_dir = ROOT / "samples" / "google"
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_path = out_dir / "phase2_batch.json"
    batch_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = []
    for item in items:
        term = ((item.get("searchQuery") or {}).get("term") or "").strip()
        organic = item.get("organicResults") or []
        retailers = {"bigbasket": [], "flipkart": []}
        for result in organic:
            url = result.get("url") or ""
            kind = retailer_from_url(url)
            if kind:
                retailers[kind].append(
                    {
                        "title": result.get("title"),
                        "url": url,
                        "description": result.get("description"),
                    }
                )
        per_gtin = out_dir / f"{term}.json"
        if term:
            per_gtin.write_text(json.dumps([item], indent=2, ensure_ascii=False), encoding="utf-8")
        summary.append(
            {
                "gtin": term,
                "organic_count": len(organic),
                "bigbasket_hits": len(retailers["bigbasket"]),
                "flipkart_hits": len(retailers["flipkart"]),
                "bigbasket_urls": [x["url"] for x in retailers["bigbasket"]],
                "flipkart_urls": [x["url"] for x in retailers["flipkart"]],
                "top_title": (organic[0].get("title") if organic else None),
            }
        )
        print(
            f"{term}: organic={len(organic)} "
            f"bigbasket={len(retailers['bigbasket'])} flipkart={len(retailers['flipkart'])}"
        )

    summary_path = ROOT / "samples" / "google" / "phase2_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved batch to {batch_path}")
    print(f"Saved summary to {summary_path}")
    print(f"Apify dataset: https://console.apify.com/storage/datasets/{dataset_id}")


if __name__ == "__main__":
    main()
