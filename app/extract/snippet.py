"""Parse name / price / weight from a Google organic result (snippet + productInfo)."""

from __future__ import annotations

import re

from app.normalize import parse_money, parse_weight, product_name, short_description

_RATE_RE = re.compile(r"Rate\s*:?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_MRP_RE = re.compile(r"MRP\s*:?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_RS_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_SKIP_PRICE_CONTEXT_RE = re.compile(
    r"(delivery|shipping|orders?\s+above|cashback|\d+\s*%\s*off)",
    re.IGNORECASE,
)


def _price_from_product_info(info: dict | None) -> float | None:
    if not isinstance(info, dict) or not info:
        return None
    raw = info.get("price")
    if isinstance(raw, dict):
        raw = raw.get("amount") or raw.get("value") or raw.get("sp")
    return parse_money(raw)


def _price_from_text(blob: str) -> float | None:
    rate = _RATE_RE.search(blob)
    if rate:
        return parse_money(rate.group(1))
    mrp = _MRP_RE.search(blob)
    if mrp:
        return parse_money(mrp.group(1))
    for match in _RS_RE.finditer(blob):
        window = blob[max(0, match.start() - 40) : min(len(blob), match.end() + 40)]
        if _SKIP_PRICE_CONTEXT_RE.search(window):
            continue
        return parse_money(match.group(1))
    return None


def extract_from_snippet(
    title: str,
    description: str,
    product_info: dict | None = None,
) -> dict:
    blob = f"{title} {description}"
    price = _price_from_product_info(product_info)
    if price is None:
        price = _price_from_text(blob)

    name = title.split("Rate")[0].split("Price in India")[0].strip(" -|")
    name = re.sub(r"^\d{8,14}\s*-\s*", "", name).strip() or None

    return {
        "product_name": product_name(None, name),
        "price": {"amount": price, "currency": "INR"} if price is not None else None,
        "weight": parse_weight(blob),
        "description": short_description(description),
        "source": "google:snippet",
    }
