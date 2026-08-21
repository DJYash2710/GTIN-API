"""Shared Apify Google Search input.

One billed search page: desktop SERP, India (google.co.in).
Query is the GTIN only — no site:/inurl: filters, no retailer PDP scrape.
Desktop is required so Google's product rich results (price, stock, rating)
show up in organic `productInfo`.
"""

from __future__ import annotations

# Actor keys that would add Google operators or scrape landing pages.
_BLOCKED_INPUT_KEYS = (
    "site",
    "relatedToSite",
    "wordsInUrl",
    "wordsInTitle",
    "wordsInText",
    "websiteContentScraper",
)


def google_run_input(queries: str) -> dict:
    payload = {
        "queries": queries,
        "countryCode": "in",
        "languageCode": "en",
        "mobileResults": False,
        "maxPagesPerQuery": 1,
        "focusOnPaidAds": False,
        "saveHtml": False,
        "saveHtmlToKeyValueStore": False,
        "includeIcons": False,
    }
    for key in _BLOCKED_INPUT_KEYS:
        payload.pop(key, None)
    return payload
