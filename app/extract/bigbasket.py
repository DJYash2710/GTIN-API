"""Extract name, price, weight, description from saved BigBasket product JSON."""

from __future__ import annotations

from app.normalize import parse_money, parse_weight, product_name, short_description


_DESC_TITLES = ("about the product", "from the brand", "features")
_SKIP_TITLES = {"ingredients", "nutritional facts", "other product info", "how to use", "storage"}


def _about_tab(payload: dict) -> str | None:
    tabs = payload.get("tabs") or []
    by_title = {(tab.get("title") or "").strip().lower(): tab for tab in tabs}
    for title in _DESC_TITLES:
        if title in by_title:
            return by_title[title].get("content")
    for tab in tabs:
        title = (tab.get("title") or "").strip().lower()
        if title and title not in _SKIP_TITLES:
            return tab.get("content")
    return None


def extract_bigbasket(payload: dict) -> dict:
    brand = ((payload.get("brand") or {}).get("name")) if isinstance(payload.get("brand"), dict) else None
    desc = payload.get("desc")
    pricing = ((payload.get("pricing") or {}).get("discount") or {})
    prim = pricing.get("prim_price") or {}
    amount = parse_money(prim.get("sp") or pricing.get("mrp"))

    return {
        "product_name": product_name(brand, desc),
        "price": {"amount": amount, "currency": "INR"} if amount is not None else None,
        "weight": parse_weight(payload.get("w") or ""),
        "description": short_description(_about_tab(payload) or payload.get("usp")),
        "source": "apify:bigbasket",
        "retailer_id": payload.get("id"),
        "path": payload.get("absolute_url"),
    }
