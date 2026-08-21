"""Host priority for Google organic results (India grocery)."""

from __future__ import annotations

from urllib.parse import urlparse

# Lower number = try first. Hosts not listed are ignored as product pages
# except as a last-resort snippet parse.
HOST_PRIORITY: list[tuple[str, str]] = [
    ("bigbasket.com", "bigbasket"),
    ("jiomart.com", "jiomart"),
    ("amazon.in", "amazon_in"),
    ("flipkart.com", "flipkart"),
    ("starquik.com", "starquik"),
    ("openfoodfacts.org", "openfoodfacts"),
]

SKIP_HOSTS = (
    "barcode-list.com",
    "digit-eyes.com",
    "buycott.com",
    "upcitemdb.com",
    "upcindex.com",
    "barcodespider.com",
    "instagram.com",
    "youtube.com",
    "facebook.com",
    "mustakshif",
    "amazon.com",
    "amazon.eg",
)


def hostname(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]
    return host


def source_priority_index(source: str) -> int:
    token = (source or "").rsplit(":", 1)[-1]
    for i, (_, sid) in enumerate(HOST_PRIORITY):
        if sid == token:
            return i
    return 99


def source_for_url(url: str) -> str | None:
    host = hostname(url)
    for suffix, source_id in HOST_PRIORITY:
        if host == suffix or host.endswith("." + suffix):
            return source_id
    return None


def is_skipped_host(url: str) -> bool:
    host = hostname(url)
    return any(skip in host for skip in SKIP_HOSTS)


def looks_like_product_url(url: str, source_id: str) -> bool:
    path = urlparse(url).path.lower()
    # BigBasket / Flipkart: do not require /pd/ or /p/ (no inurl-style path filter).
    if source_id in {"bigbasket", "flipkart"}:
        return True
    if source_id == "jiomart":
        return "/p/" in path
    if source_id == "amazon_in":
        return "/dp/" in path or "/gp/product/" in path
    if source_id == "starquik":
        return "/p/" in path or "/product" in path
    if source_id == "openfoodfacts":
        return "/product/" in path
    return False
