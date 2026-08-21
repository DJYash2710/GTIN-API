"""Resolve a GTIN using only files under samples/. Never calls Apify."""

from __future__ import annotations

import json
from pathlib import Path

from app.gtin import is_valid_gtin, normalize_gtin
from app.resolve import product_from_google_item

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def _load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _google_item_for_gtin(gtin: str) -> dict | None:
    for name in (f"{gtin}_mobile.json", f"{gtin}.json"):
        payload = _load_json(SAMPLES / "google" / name)
        if isinstance(payload, list) and payload:
            for item in payload:
                term = ((item.get("searchQuery") or {}).get("term") or "").strip()
                if term == gtin:
                    return item
            return payload[0]
    batch = _load_json(SAMPLES / "google" / "phase2_batch.json") or []
    for item in batch:
        term = ((item.get("searchQuery") or {}).get("term") or "").strip()
        if term == gtin:
            return item
    return None


def _bigbasket_by_path() -> dict[str, dict]:
    batch = _load_json(SAMPLES / "bigbasket" / "phase2_batch.json") or []
    index: dict[str, dict] = {}
    for product in batch:
        path = (product.get("absolute_url") or "").split("?")[0].rstrip("/")
        if path:
            index[path] = product
            parts = path.split("/")
            if len(parts) >= 3 and parts[1] == "pd":
                index[f"/pd/{parts[2]}"] = product
    return index


def resolve_from_samples(raw_gtin: str) -> dict:
    gtin = normalize_gtin(raw_gtin)
    if not is_valid_gtin(gtin):
        return {"error": "invalid_gtin", "gtin": raw_gtin}

    google_item = _google_item_for_gtin(gtin)
    if not google_item:
        return {"gtin": gtin, "error": "no_local_sample"}

    return product_from_google_item(
        gtin,
        google_item,
        cache="sample",
        bb_index=_bigbasket_by_path(),
    )
