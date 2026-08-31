"""Live Apify is on by default. Set APIFY_ENABLED=false to use samples only.

GET spends credits on a cache miss or a stale price.
Collect scripts also need --confirm.
"""

from __future__ import annotations

import os


def apify_is_enabled() -> bool:
    raw = os.getenv("APIFY_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def require_apify() -> None:
    if not apify_is_enabled():
        raise SystemExit(
            "Apify is disabled. Set APIFY_ENABLED=true (default) or add your token. "
            "Use saved files under samples/ when live search is off."
        )
