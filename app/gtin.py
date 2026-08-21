"""GTIN-8/12/13/14 checksum validation."""

from __future__ import annotations


def normalize_gtin(raw: str) -> str:
    return "".join(ch for ch in raw.strip() if ch.isdigit())


def is_valid_gtin(raw: str) -> bool:
    digits = normalize_gtin(raw)
    if len(digits) not in {8, 12, 13, 14}:
        return False
    body, check = digits[:-1], int(digits[-1])
    total = 0
    for i, ch in enumerate(reversed(body)):
        n = int(ch)
        total += n * (3 if i % 2 == 0 else 1)
    return (10 - (total % 10)) % 10 == check
