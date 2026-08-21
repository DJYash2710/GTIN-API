"""Live Google Search via Apify. Call only when the HTTP client sends force_refresh=true."""

from __future__ import annotations

import os

from apify_client import ApifyClient

from app.apify_google import google_run_input
from app.credits import apify_is_enabled
from app.resolve import product_from_google_item


def _dataset_id(run) -> str | None:
    if run is None:
        return None
    return getattr(run, "default_dataset_id", None) or (
        run.get("defaultDatasetId") if isinstance(run, dict) else None
    )


def google_search_gtin(gtin: str) -> dict | None:
    """One billed Google page (desktop, India). Does not scrape retailer PDPs."""
    if not apify_is_enabled():
        raise RuntimeError("apify_disabled")
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        raise RuntimeError("missing_apify_token")
    actor = os.getenv("APIFY_GOOGLE_ACTOR_ID") or os.getenv(
        "APIFY_GOOGLE_ACTOR", "nFJndFXA5zjCTuudP"
    )
    client = ApifyClient(token)
    run = client.actor(actor).call(run_input=google_run_input(gtin))
    dataset_id = _dataset_id(run)
    if not dataset_id:
        return None
    items = list(client.dataset(dataset_id).iterate_items())
    for item in items:
        term = ((item.get("searchQuery") or {}).get("term") or "").strip()
        if term == gtin:
            return item
    return items[0] if items else None


def resolve_live(gtin: str) -> dict:
    if not apify_is_enabled():
        return {"gtin": gtin, "error": "apify_disabled"}
    try:
        google_item = google_search_gtin(gtin)
    except RuntimeError as exc:
        return {"gtin": gtin, "error": str(exc)}
    if not google_item:
        return {"gtin": gtin, "error": "not_found"}
    return product_from_google_item(gtin, google_item, cache="miss")
