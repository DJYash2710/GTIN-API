"""Resolve a GTIN from saved samples only. Does not call Apify."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.resolve_samples import resolve_from_samples  # noqa: E402


def main() -> None:
    gtin = sys.argv[1] if len(sys.argv) > 1 else "8901719123870"
    result = resolve_from_samples(gtin)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
