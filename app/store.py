"""Master catalog, lookup cache, and source-confidence scores.

Production: MySQL (set MYSQL_HOST). Tests/local without MySQL use an in-memory store.

Confirmed products live in `master_gtin`. Live/sample GET payloads live in `lookup_cache`
with independent name/weight vs price TTLs (PRD §10).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

_lock = threading.Lock()
_mysql_conn = None
_memory: dict[str, Any] | None = None

MASTER_TABLE = "master_gtin"

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {MASTER_TABLE} (
    gtin VARCHAR(14) PRIMARY KEY,
    name VARCHAR(512) NULL,
    price_amount DECIMAL(12, 4) NULL,
    price_currency VARCHAR(8) NOT NULL DEFAULT 'INR',
    weight_value DECIMAL(12, 4) NULL,
    weight_unit VARCHAR(8) NULL,
    name_source VARCHAR(64) NULL,
    price_source VARCHAR(64) NULL,
    weight_source VARCHAR(64) NULL,
    updated_at DATETIME(6) NOT NULL,
    name_updated_at DATETIME(6) NULL,
    price_updated_at DATETIME(6) NULL
);

CREATE TABLE IF NOT EXISTS lookup_cache (
    gtin VARCHAR(14) PRIMARY KEY,
    payload JSON NOT NULL,
    name_resolved_at DATETIME(6) NOT NULL,
    price_resolved_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL
);

CREATE TABLE IF NOT EXISTS source_confidence (
    source VARCHAR(64) PRIMARY KEY,
    score INT NOT NULL DEFAULT 0
);
"""

_MIGRATIONS = [
    f"ALTER TABLE {MASTER_TABLE} ADD COLUMN name_updated_at DATETIME(6) NULL",
    f"ALTER TABLE {MASTER_TABLE} ADD COLUMN price_updated_at DATETIME(6) NULL",
]


def mysql_configured() -> bool:
    return bool(os.getenv("MYSQL_HOST", "").strip())


def backend_name() -> str:
    return "mysql" if mysql_configured() else "memory"


def name_ttl() -> timedelta:
    return timedelta(days=int(os.getenv("NAME_TTL_DAYS", "30")))


def price_ttl() -> timedelta:
    return timedelta(hours=float(os.getenv("PRICE_TTL_HOURS", "12")))


def reset_connection() -> None:
    global _mysql_conn, _memory
    with _lock:
        if _mysql_conn is not None:
            try:
                _mysql_conn.close()
            except Exception:
                pass
            _mysql_conn = None
        _memory = _empty_memory()


def _empty_memory() -> dict[str, Any]:
    return {"master_gtin": {}, "confidence": {}, "lookups": {}}


def _memory_store() -> dict[str, Any]:
    global _memory
    if _memory is None:
        _memory = _empty_memory()
    # Migrate older in-memory key if a long-lived process still has it.
    if "products" in _memory and "master_gtin" not in _memory:
        _memory["master_gtin"] = _memory.pop("products")
    return _memory


def _safe_ident(name: str, fallback: str) -> str:
    cleaned = (name or "").strip() or fallback
    if not all(ch.isalnum() or ch == "_" for ch in cleaned):
        raise ValueError(f"Invalid MySQL identifier: {name!r}")
    return cleaned


def _rename_legacy_products_table(cur) -> None:
    """If an old `products` table exists and `master_gtin` does not, rename it."""
    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'products'
        """
    )
    has_products = int((cur.fetchone() or {}).get("n") or 0) > 0
    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = %s
        """,
        (MASTER_TABLE,),
    )
    has_master = int((cur.fetchone() or {}).get("n") or 0) > 0
    if has_products and not has_master:
        cur.execute(f"RENAME TABLE products TO `{MASTER_TABLE}`")


def _mysql():
    global _mysql_conn
    import pymysql
    from pymysql.cursors import DictCursor

    if _mysql_conn is not None:
        try:
            _mysql_conn.ping(reconnect=True)
            return _mysql_conn
        except Exception:
            _mysql_conn = None
    database = _safe_ident(os.getenv("MYSQL_DATABASE", "gtin"), "gtin")
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1").strip(),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "gtin").strip(),
        password=os.getenv("MYSQL_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=DictCursor,
    )
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.execute(f"USE `{database}`")
        _rename_legacy_products_table(cur)
        for statement in _SCHEMA.strip().split(";"):
            sql = statement.strip()
            if sql:
                cur.execute(sql)
        for sql in _MIGRATIONS:
            try:
                cur.execute(sql)
            except Exception as exc:
                if getattr(exc, "args", None) and exc.args[0] == 1060:
                    continue
                # 1146 = table doesn't exist yet during odd race; ignore rename-related
                if getattr(exc, "args", None) and exc.args[0] == 1146:
                    continue
                raise
    conn.commit()
    _mysql_conn = conn
    return conn


def _as_float(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _as_utc(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        value = datetime.fromisoformat(text)
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_fresh(stamp: datetime | str | None, ttl: timedelta) -> bool:
    parsed = _as_utc(stamp)
    if parsed is None:
        return False
    return datetime.now(timezone.utc) - parsed <= ttl


def increment_source(source: str | None) -> None:
    if not source:
        return
    if not mysql_configured():
        scores = _memory_store()["confidence"]
        scores[source] = int(scores.get(source) or 0) + 1
        return
    conn = _mysql()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_confidence (source, score) VALUES (%s, 1)
            ON DUPLICATE KEY UPDATE score = score + 1
            """,
            (source,),
        )


def save_product(gtin: str, payload: dict, sources: dict[str, str | None]) -> dict:
    now = datetime.now(timezone.utc)
    name = payload.get("name")
    price = payload.get("price") or {}
    weight = payload.get("weight") or {}
    row = {
        "gtin": gtin,
        "name": name,
        "price_amount": price.get("amount"),
        "price_currency": price.get("currency") or "INR",
        "weight_value": weight.get("value"),
        "weight_unit": weight.get("unit"),
        "name_source": sources.get("name"),
        "price_source": sources.get("price"),
        "weight_source": sources.get("weight"),
        "updated_at": now.isoformat(),
        "name_updated_at": now.isoformat(),
        "price_updated_at": now.isoformat(),
    }
    with _lock:
        for source in (sources.get("name"), sources.get("price"), sources.get("weight")):
            increment_source(source)
        if mysql_configured():
            conn = _mysql()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO master_gtin (
                        gtin, name, price_amount, price_currency, weight_value, weight_unit,
                        name_source, price_source, weight_source, updated_at,
                        name_updated_at, price_updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        price_amount = VALUES(price_amount),
                        price_currency = VALUES(price_currency),
                        weight_value = VALUES(weight_value),
                        weight_unit = VALUES(weight_unit),
                        name_source = VALUES(name_source),
                        price_source = VALUES(price_source),
                        weight_source = VALUES(weight_source),
                        updated_at = VALUES(updated_at),
                        name_updated_at = VALUES(name_updated_at),
                        price_updated_at = VALUES(price_updated_at)
                    """,
                    (
                        gtin,
                        name,
                        price.get("amount"),
                        price.get("currency") or "INR",
                        weight.get("value"),
                        weight.get("unit"),
                        sources.get("name"),
                        sources.get("price"),
                        sources.get("weight"),
                        now,
                        now,
                        now,
                    ),
                )
            conn.commit()
        else:
            _memory_store()["master_gtin"][gtin] = row
    return get_product(gtin) or {}


def update_product_price(gtin: str, price: dict | None, source: str | None) -> dict | None:
    """Refresh only the price on a confirmed product (name/weight TTLs stay)."""
    existing = get_product(gtin)
    if existing is None:
        return None
    now = datetime.now(timezone.utc)
    amount = None if price is None else price.get("amount")
    currency = (None if price is None else price.get("currency")) or "INR"
    with _lock:
        if mysql_configured():
            conn = _mysql()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE master_gtin
                    SET price_amount = %s, price_currency = %s, price_source = %s,
                        price_updated_at = %s, updated_at = %s
                    WHERE gtin = %s
                    """,
                    (amount, currency, source, now, now, gtin),
                )
            conn.commit()
        else:
            row = _memory_store()["master_gtin"].get(gtin)
            if row is None:
                return None
            row["price_amount"] = amount
            row["price_currency"] = currency
            row["price_source"] = source
            row["price_updated_at"] = now.isoformat()
            row["updated_at"] = now.isoformat()
    return get_product(gtin)


def _row_to_product(row: dict) -> dict:
    price = None
    amount = _as_float(row.get("price_amount"))
    if amount is not None:
        price = {"amount": amount, "currency": row.get("price_currency") or "INR"}
    weight = None
    value = _as_float(row.get("weight_value"))
    if value is not None:
        weight = {"value": value, "unit": row.get("weight_unit")}
    updated = row.get("updated_at")
    if hasattr(updated, "isoformat"):
        updated = updated.isoformat()
    name_updated = row.get("name_updated_at") or updated
    price_updated = row.get("price_updated_at") or updated
    if hasattr(name_updated, "isoformat"):
        name_updated = name_updated.isoformat()
    if hasattr(price_updated, "isoformat"):
        price_updated = price_updated.isoformat()
    return {
        "gtin": row["gtin"],
        "name": row.get("name"),
        "price": price,
        "weight": weight,
        "sources": {
            "name": row.get("name_source"),
            "price": row.get("price_source"),
            "weight": row.get("weight_source"),
        },
        "updated_at": updated,
        "name_updated_at": name_updated,
        "price_updated_at": price_updated,
    }


def get_product(gtin: str) -> dict | None:
    if not mysql_configured():
        row = _memory_store()["master_gtin"].get(gtin)
        return _row_to_product(row) if row else None
    conn = _mysql()
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM `{MASTER_TABLE}` WHERE gtin = %s", (gtin,))
        row = cur.fetchone()
    if row is None:
        return None
    return _row_to_product(row)


def _payload_fields(payload: dict) -> dict:
    return {
        "name": list(payload.get("name") or []),
        "name_source": list(payload.get("name_source") or []),
        "price": list(payload.get("price") or []),
        "price_source": list(payload.get("price_source") or []),
        "weight": list(payload.get("weight") or []),
        "weight_source": list(payload.get("weight_source") or []),
    }


def save_lookup(
    gtin: str,
    payload: dict,
    *,
    update_name: bool = True,
    update_price: bool = True,
    name_resolved_at: datetime | None = None,
    price_resolved_at: datetime | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    fields = _payload_fields(payload)
    existing = get_lookup(gtin)
    if existing is not None and not update_name:
        fields["name"] = existing["payload"]["name"]
        fields["name_source"] = existing["payload"]["name_source"]
        fields["weight"] = existing["payload"]["weight"]
        fields["weight_source"] = existing["payload"]["weight_source"]
    if existing is not None and not update_price:
        fields["price"] = existing["payload"]["price"]
        fields["price_source"] = existing["payload"]["price_source"]

    name_at = name_resolved_at or now
    price_at = price_resolved_at or now
    if existing is not None and not update_name:
        name_at = _as_utc(existing["name_resolved_at"]) or name_at
    if existing is not None and not update_price:
        price_at = _as_utc(existing["price_resolved_at"]) or price_at

    row = {
        "gtin": gtin,
        "payload": fields,
        "name_resolved_at": name_at.isoformat() if hasattr(name_at, "isoformat") else name_at,
        "price_resolved_at": price_at.isoformat() if hasattr(price_at, "isoformat") else price_at,
        "updated_at": now.isoformat(),
    }
    with _lock:
        if mysql_configured():
            conn = _mysql()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lookup_cache (
                        gtin, payload, name_resolved_at, price_resolved_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        payload = VALUES(payload),
                        name_resolved_at = VALUES(name_resolved_at),
                        price_resolved_at = VALUES(price_resolved_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (gtin, json.dumps(fields), name_at, price_at, now),
                )
            conn.commit()
        else:
            _memory_store()["lookups"][gtin] = row
    return get_lookup(gtin) or row


def _parse_payload(raw) -> dict:
    if raw is None:
        return _payload_fields({})
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        raw = json.loads(raw)
    return _payload_fields(raw)


def get_lookup(gtin: str) -> dict | None:
    if not mysql_configured():
        row = _memory_store()["lookups"].get(gtin)
        if row is None:
            return None
        payload = _payload_fields(row["payload"])
        name_at = row["name_resolved_at"]
        price_at = row["price_resolved_at"]
    else:
        conn = _mysql()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM lookup_cache WHERE gtin = %s", (gtin,))
            row = cur.fetchone()
        if row is None:
            return None
        payload = _parse_payload(row.get("payload"))
        name_at = row["name_resolved_at"]
        price_at = row["price_resolved_at"]
    return {
        "gtin": gtin,
        "payload": payload,
        "name_resolved_at": name_at,
        "price_resolved_at": price_at,
        "name_fresh": is_fresh(name_at, name_ttl()),
        "price_fresh": is_fresh(price_at, price_ttl()),
    }


def delete_cache(gtin: str, *, master: bool = True) -> dict:
    """Drop lookup cache, and optionally the confirmed master row."""
    deleted_lookup = False
    deleted_master = False
    with _lock:
        if mysql_configured():
            conn = _mysql()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM lookup_cache WHERE gtin = %s", (gtin,))
                deleted_lookup = cur.rowcount > 0
                if master:
                    cur.execute(f"DELETE FROM `{MASTER_TABLE}` WHERE gtin = %s", (gtin,))
                    deleted_master = cur.rowcount > 0
            conn.commit()
        else:
            mem = _memory_store()
            deleted_lookup = mem["lookups"].pop(gtin, None) is not None
            if master:
                deleted_master = mem["master_gtin"].pop(gtin, None) is not None
    return {
        "gtin": gtin,
        "lookup": deleted_lookup,
        "master": deleted_master,
    }


def all_confidence() -> dict[str, int]:
    if not mysql_configured():
        scores = _memory_store()["confidence"]
        return dict(sorted(scores.items(), key=lambda item: (-item[1], item[0])))
    conn = _mysql()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT source, score FROM source_confidence ORDER BY score DESC, source"
        )
        rows = cur.fetchall()
    return {row["source"]: int(row["score"]) for row in rows}


def product_as_lookup(product: dict) -> dict:
    """Shape a stored master row as GET /v1/products field arrays."""
    sources = product.get("sources") or {}
    name = product.get("name")
    price = product.get("price")
    weight = product.get("weight")

    def src(has_value, key: str) -> list[str]:
        if not has_value:
            return []
        return [sources.get(key) or "master"]

    return {
        "gtin": product["gtin"],
        "name": [name] if name else [],
        "name_source": src(bool(name), "name"),
        "price": [price] if price else [],
        "price_source": src(bool(price), "price"),
        "weight": [weight] if weight else [],
        "weight_source": src(bool(weight), "weight"),
        "cache": "hit",
    }
