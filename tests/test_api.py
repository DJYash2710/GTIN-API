from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-local-key"}
GTIN = "8901719123870"


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["apify_enabled"] is False
    assert res.json()["live"] == "on cache miss only"
    assert res.json()["db"] == "memory"
    assert res.json()["mode"] == "cache-then-live"


def test_missing_token():
    res = client.get(f"/v1/products/{GTIN}")
    assert res.status_code == 401


def test_bad_token():
    res = client.get(f"/v1/products/{GTIN}", headers={"Authorization": "Bearer wrong"})
    assert res.status_code == 401


def test_invalid_gtin():
    res = client.get("/v1/products/123", headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_gtin"


def test_known_sample_parle_g():
    res = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert res.status_code == 200
    body = res.json()
    assert body["gtin"] == GTIN
    assert "data" not in body
    assert 1 <= len(body["name"]) <= 3
    assert len(body["name"]) == len(body["name_source"])
    assert 1 <= len(body["price"]) <= 3
    assert len(body["price"]) == len(body["price_source"])
    assert 1 <= len(body["weight"]) <= 3
    assert len(body["weight"]) == len(body["weight_source"])
    assert body["name"][0]
    assert body["price"][0]["currency"] == "INR"
    assert body["weight"][0]["unit"] in {"g", "ml"}
    assert body["cache"] == "sample"


def test_cache_miss_uses_live_when_apify_enabled(monkeypatch):
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "apify_is_enabled", lambda: True)
    called = {"live": False}

    def fake_live(gtin: str) -> dict:
        called["live"] = True
        return {
            "gtin": gtin,
            "name": ["From live"],
            "name_source": ["google:bigbasket"],
            "price": [{"amount": 10.0, "currency": "INR"}],
            "price_source": ["google:bigbasket"],
            "weight": [{"value": 100, "unit": "g"}],
            "weight_source": ["google:bigbasket"],
            "cache": "miss",
        }

    monkeypatch.setattr(main_mod, "resolve_live", fake_live)
    res = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert res.status_code == 200
    assert called["live"] is True
    assert res.json()["name"][0] == "From live"
    assert res.json()["cache"] == "miss"


def test_cache_hit_skips_live(monkeypatch):
    from app import main as main_mod, store

    store.save_product(
        GTIN,
        {
            "name": "Cached Name",
            "price": {"amount": 1, "currency": "INR"},
            "weight": {"value": 10, "unit": "g"},
        },
        {"name": "google:bigbasket", "price": "google:bigbasket", "weight": "google:bigbasket"},
    )
    monkeypatch.setattr(main_mod, "apify_is_enabled", lambda: True)

    def boom(gtin: str) -> dict:
        raise AssertionError("live search should not run on cache hit")

    monkeypatch.setattr(main_mod, "resolve_live", boom)
    res = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert res.status_code == 200
    assert res.json()["cache"] == "hit"
    assert res.json()["name"] == ["Cached Name"]


def test_unknown_valid_gtin_is_404():
    # Valid checksum, not in samples or cache.
    res = client.get("/v1/products/8900000000005", headers=AUTH)
    assert res.status_code == 404
