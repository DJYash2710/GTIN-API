"""Live Apify is off unless APIFY_ENABLED is true.

GET spends credits only on a cache miss, a stale price, or force_refresh=true.
Collect scripts also need --confirm.
"""

from __future__ import annotations

import os


def apify_is_enabled() -> bool:
    return os.getenv("APIFY_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def require_apify() -> None:
    if not apify_is_enabled():
        raise SystemExit(
            "Apify is disabled. Set APIFY_ENABLED=true only when you have credits. "
            "Use saved files under samples/ instead."
        )
