from __future__ import annotations

import re
from html.parser import HTMLParser


_WEIGHT_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|gm|ml|l|ltr|litre|liter)\b",
    re.IGNORECASE,
)


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"style", "script"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self.parts.append(text)


def strip_html(raw: str) -> str:
    parser = _HTMLText()
    parser.feed(raw or "")
    text = " ".join(parser.parts)
    return re.sub(r"\s+", " ", text).strip()


def parse_weight(raw: str) -> dict | None:
    if not raw:
        return None
    match = _WEIGHT_RE.search(raw.replace(",", ""))
    if not match:
        return None
    value = float(match.group("value"))
    unit = match.group("unit").lower()
    if unit == "kg":
        return {"value": round(value * 1000, 3), "unit": "g", "original": raw.strip()}
    if unit in {"g", "gm"}:
        return {"value": value, "unit": "g", "original": raw.strip()}
    if unit == "ml":
        return {"value": value, "unit": "ml", "original": raw.strip()}
    if unit in {"l", "ltr", "litre", "liter"}:
        return {"value": round(value * 1000, 3), "unit": "ml", "original": raw.strip()}
    return None


def parse_money(raw: str | int | float | None) -> float | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = re.sub(r"[^\d.]", "", str(raw))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def product_name(brand: str | None, desc: str | None) -> str | None:
    brand = (brand or "").strip()
    desc = (desc or "").strip()
    if not brand and not desc:
        return None
    if brand and desc.lower().startswith(brand.lower()):
        return desc
    if brand and desc:
        return f"{brand} {desc}"
    return brand or desc


def short_description(text: str | None, limit: int = 350) -> str | None:
    cleaned = strip_html(text or "")
    cleaned = re.sub(r"@import[^;]+;", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"
