from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-local-key"}
GTIN = "8901719123870"

PAYLOAD = {
    "name": ["Cached Name"],
    "name_source": ["google:bigbasket"],
    "price": [{"amount": 1.0, "currency": "INR"}],
    "price_source": ["google:bigbasket"],
    "weight": [{"value": 10.0, "unit": "g"}],
    "weight_source": ["google:bigbasket"],
}


def test_second_get_uses_lookup_cache(monkeypatch):
    first = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert first.status_code == 200
    assert first.json()["cache"] == "sample"

    from app import main as main_mod

    monkeypatch.setattr(main_mod, "apify_is_enabled", lambda: True)

    def boom(gtin: str) -> dict:
        raise AssertionError("live search should not run on lookup cache hit")

    monkeypatch.setattr(main_mod, "resolve_live", boom)
    second = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert second.status_code == 200
    body = second.json()
    assert body["cache"] == "hit"
    assert body["name"] == first.json()["name"]
    assert body["price"] == first.json()["price"]


def test_stale_price_refreshes_live_keeps_name(monkeypatch):
    from app import main as main_mod, store

    now = datetime.now(timezone.utc)
    store.save_lookup(
        GTIN,
        PAYLOAD,
        name_resolved_at=now,
        price_resolved_at=now - timedelta(hours=13),
    )
    monkeypatch.setattr(main_mod, "apify_is_enabled", lambda: True)

    def fake_live(gtin: str) -> dict:
        return {
            "gtin": gtin,
            "name": ["Should not replace"],
            "name_source": ["google:amazon"],
            "price": [{"amount": 99.0, "currency": "INR"}],
            "price_source": ["google:amazon"],
            "weight": [{"value": 999.0, "unit": "g"}],
            "weight_source": ["google:amazon"],
            "cache": "miss",
        }

    monkeypatch.setattr(main_mod, "resolve_live", fake_live)
    res = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert res.status_code == 200
    body = res.json()
    assert body["cache"] == "miss"
    assert body["name"] == ["Cached Name"]
    assert body["weight"][0]["value"] == 10.0
    assert body["price"][0]["amount"] == 99.0
    assert body["price_source"] == ["google:amazon"]


def test_stale_price_without_apify_keeps_cache():
    from app import store

    now = datetime.now(timezone.utc)
    store.save_lookup(
        GTIN,
        PAYLOAD,
        name_resolved_at=now,
        price_resolved_at=now - timedelta(hours=13),
    )
    res = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert res.status_code == 200
    body = res.json()
    assert body["cache"] == "hit"
    assert body["price"][0]["amount"] == 1.0


def test_stale_name_does_full_refetch(monkeypatch):
    from app import main as main_mod, store

    now = datetime.now(timezone.utc)
    store.save_lookup(
        GTIN,
        PAYLOAD,
        name_resolved_at=now - timedelta(days=31),
        price_resolved_at=now,
    )
    monkeypatch.setattr(main_mod, "apify_is_enabled", lambda: True)

    def fake_live(gtin: str) -> dict:
        return {
            "gtin": gtin,
            "name": ["Fresh Name"],
            "name_source": ["google:amazon"],
            "price": [{"amount": 50.0, "currency": "INR"}],
            "price_source": ["google:amazon"],
            "weight": [{"value": 100.0, "unit": "g"}],
            "weight_source": ["google:amazon"],
            "cache": "miss",
        }

    monkeypatch.setattr(main_mod, "resolve_live", fake_live)
    res = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert res.status_code == 200
    body = res.json()
    assert body["cache"] == "miss"
    assert body["name"] == ["Fresh Name"]
    assert body["price"][0]["amount"] == 50.0


def test_invalidate_clears_lookup_and_master():
    first = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert first.json()["cache"] == "sample"
    client.post(
        f"/v1/products/{GTIN}/confirm",
        headers=AUTH,
        json={
            "name": {"value": "Confirmed", "source": "google:bigbasket", "custom": False},
            "price": {"amount": 22, "currency": "INR", "source": "google:bigbasket", "custom": False},
            "weight": {"value": 250, "unit": "g", "source": "google:bigbasket", "custom": False},
        },
    )
    hit = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert hit.json()["cache"] == "hit"

    inv = client.delete(f"/v1/products/{GTIN}/cache", headers=AUTH)
    assert inv.status_code == 200
    assert inv.json()["lookup"] is True
    assert inv.json()["master"] is True

    after = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert after.status_code == 200
    assert after.json()["cache"] == "sample"


def test_confirmed_stale_price_updates_from_live(monkeypatch):
    from app import main as main_mod, store

    store.save_product(
        GTIN,
        {
            "name": "Confirmed Name",
            "price": {"amount": 1, "currency": "INR"},
            "weight": {"value": 10, "unit": "g"},
        },
        {"name": "google:bigbasket", "price": "google:bigbasket", "weight": "google:bigbasket"},
    )
    mem = store._memory_store()["master_gtin"][GTIN]
    mem["price_updated_at"] = (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()

    monkeypatch.setattr(main_mod, "apify_is_enabled", lambda: True)

    def fake_live(gtin: str) -> dict:
        return {
            "gtin": gtin,
            "name": ["Live Name"],
            "name_source": ["google:amazon"],
            "price": [{"amount": 77.0, "currency": "INR"}],
            "price_source": ["google:amazon"],
            "weight": [{"value": 500.0, "unit": "g"}],
            "weight_source": ["google:amazon"],
            "cache": "miss",
        }

    monkeypatch.setattr(main_mod, "resolve_live", fake_live)
    res = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert res.status_code == 200
    body = res.json()
    assert body["cache"] == "miss"
    assert body["name"] == ["Confirmed Name"]
    assert body["weight"][0]["value"] == 10.0
    assert body["price"][0]["amount"] == 77.0
    stored = store.get_product(GTIN)
    assert stored["price"]["amount"] == 77.0
    assert stored["sources"]["price"] == "google:amazon"
