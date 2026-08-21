"""Turn a Google SERP item into name/price/weight arrays (no Apify calls)."""

from __future__ import annotations

from app.extract.bigbasket import extract_bigbasket
from app.extract.google_serp import all_ranked_hits, hit_from_result, pick_best_hit
from app.extract.snippet import extract_from_snippet
from app.hosts import is_skipped_host, source_priority_index
from app import store


MAX_PER_FIELD = 3


def _snippet_from_hit(hit) -> dict:
    return extract_from_snippet(hit.title, hit.description, product_info=hit.product_info)


def _snippet_from_row(row: dict) -> dict:
    hit = hit_from_result(row)
    if hit:
        return _snippet_from_hit(hit)
    keys = row.get("emphasizedKeywords") or []
    extra = " ".join(str(k) for k in keys) if isinstance(keys, list) else str(keys or "")
    description = " ".join(part for part in [row.get("description") or "", extra] if part)
    info = row.get("productInfo") if isinstance(row.get("productInfo"), dict) else None
    return extract_from_snippet(row.get("title") or "", description, product_info=info)


def _mentions_gtin(row: dict, gtin: str) -> bool:
    keys = row.get("emphasizedKeywords") or []
    extra = " ".join(str(k) for k in keys) if isinstance(keys, list) else str(keys or "")
    blob = f"{row.get('title') or ''} {row.get('description') or ''} {extra}"
    return gtin in blob


def _offer_from_extracted(extracted: dict, source: str | None = None) -> dict | None:
    name = extracted.get("product_name")
    price = extracted.get("price")
    weight = extracted.get("weight")
    if not name and not price and not weight:
        return None
    return {
        "name": name,
        "price": price,
        "weight": weight,
        "source": source or extracted.get("source"),
        "position": extracted.get("position") or 99,
    }


def _rank_tuple(source: str, position: int, scores: dict[str, int]) -> tuple:
    return (-int(scores.get(source) or 0), source_priority_index(source), int(position or 99))


def _take_field(
    candidates: list[tuple],
    key_fn,
    scores: dict[str, int],
) -> tuple[list, list[str]]:
    ordered = sorted(candidates, key=lambda item: _rank_tuple(item[1], item[2], scores))
    values: list = []
    sources: list[str] = []
    seen: set = set()
    for value, source, _position in ordered:
        key = key_fn(value)
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
        sources.append(source)
        if len(values) >= MAX_PER_FIELD:
            break
    return values, sources


def _empty_fields(gtin: str, cache: str, error: str | None = None) -> dict:
    payload = {
        "gtin": gtin,
        "name": [],
        "name_source": [],
        "price": [],
        "price_source": [],
        "weight": [],
        "weight_source": [],
        "cache": cache,
    }
    if error:
        payload["error"] = error
    return payload


def product_from_google_item(
    gtin: str,
    google_item: dict,
    *,
    cache: str,
    bb_index: dict | None = None,
) -> dict:
    organic = google_item.get("organicResults") or []
    ranked = all_ranked_hits(organic)
    best = pick_best_hit(organic)
    offers: list[dict] = []
    seen_urls: set[str] = set()

    def add(extracted: dict, url: str | None = None, source: str | None = None, position: int = 99) -> None:
        if url and url in seen_urls:
            return
        payload = dict(extracted)
        payload["position"] = position
        offer = _offer_from_extracted(payload, source)
        if offer is None:
            return
        if url:
            seen_urls.add(url)
        offers.append(offer)

    if best and best.source == "bigbasket" and bb_index:
        path = best.url.split("bigbasket.com", 1)[-1].rstrip("/")
        product = bb_index.get(path) or bb_index.get("/".join(path.split("/")[:3]))
        if product:
            add(extract_bigbasket(product), best.url, "apify:bigbasket", best.position)

    for hit in ranked:
        add(_snippet_from_hit(hit), hit.url, f"google:{hit.source}", hit.position)

    for row in organic:
        url = (row.get("url") or "").split("?")[0]
        if not url or url in seen_urls or is_skipped_host(url):
            continue
        if gtin and not _mentions_gtin(row, gtin):
            continue
        add(_snippet_from_row(row), url, "google:snippet", int(row.get("position") or 99))

    if not offers:
        return _empty_fields(gtin, cache, "not_found")

    scores = store.all_confidence()
    names: list[tuple] = []
    prices: list[tuple] = []
    weights: list[tuple] = []
    for offer in offers:
        source = offer.get("source") or "google:snippet"
        position = int(offer.get("position") or 99)
        if offer.get("name"):
            names.append((offer["name"], source, position))
        if offer.get("price") and offer["price"].get("amount") is not None:
            prices.append((offer["price"], source, position))
        if offer.get("weight") and offer["weight"].get("value") is not None:
            weights.append((offer["weight"], source, position))

    name_vals, name_src = _take_field(names, lambda v: (v or "").strip().lower(), scores)
    price_vals, price_src = _take_field(prices, lambda v: v.get("amount"), scores)
    weight_vals, weight_src = _take_field(
        weights, lambda v: (v.get("value"), (v.get("unit") or "").lower()), scores
    )

    if not name_vals and not price_vals and not weight_vals:
        return _empty_fields(gtin, cache, "not_found")

    return {
        "gtin": gtin,
        "name": name_vals,
        "name_source": name_src,
        "price": price_vals,
        "price_source": price_src,
        "weight": weight_vals,
        "weight_source": weight_src,
        "cache": cache,
    }
