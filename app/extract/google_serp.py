"""Pick the best Google organic result using host priority."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.hosts import HOST_PRIORITY, is_skipped_host, looks_like_product_url, source_for_url


@dataclass
class SerpHit:
    source: str
    url: str
    title: str
    description: str
    position: int
    product_info: dict = field(default_factory=dict)


def _priority_index(source_id: str) -> int:
    for i, (_, sid) in enumerate(HOST_PRIORITY):
        if sid == source_id:
            return i
    return 99


def _joined_description(result: dict) -> str:
    parts = [result.get("description") or ""]
    keys = result.get("emphasizedKeywords") or []
    if isinstance(keys, list):
        parts.extend(str(k) for k in keys if k)
    elif keys:
        parts.append(str(keys))
    return " ".join(part for part in parts if part).strip()


def _usable_hit(result: dict, url: str, source: str | None) -> bool:
    if not url or not source or is_skipped_host(url):
        return False
    # BigBasket / Flipkart: no inurl-style /pd/ or /p/ requirement.
    # Google often shows the product rich result on a category breadcrumb URL.
    if source in {"bigbasket", "flipkart"}:
        return True
    if looks_like_product_url(url, source):
        return True
    info = result.get("productInfo") or {}
    return bool(isinstance(info, dict) and info.get("price"))


def hit_from_result(result: dict) -> SerpHit | None:
    url = (result.get("url") or "").split("?")[0]
    source = source_for_url(url)
    if not _usable_hit(result, url, source):
        return None
    info = result.get("productInfo")
    return SerpHit(
        source=source or "web",
        url=url,
        title=result.get("title") or "",
        description=_joined_description(result),
        position=int(result.get("position") or 99),
        product_info=info if isinstance(info, dict) else {},
    )


def pick_best_hit(organic_results: list[dict]) -> SerpHit | None:
    ranked = all_ranked_hits(organic_results)
    return ranked[0] if ranked else None


def all_ranked_hits(organic_results: list[dict]) -> list[SerpHit]:
    hits: list[SerpHit] = []
    seen: set[str] = set()
    for result in organic_results or []:
        hit = hit_from_result(result)
        if hit is None or hit.url in seen:
            continue
        seen.add(hit.url)
        hits.append(hit)
    hits.sort(key=lambda item: (_priority_index(item.source), item.position))
    return hits
