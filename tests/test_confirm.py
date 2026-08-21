from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-local-key"}
GTIN = "8901719123870"


def test_ui_home_is_public():
    res = client.get("/")
    assert res.status_code == 200
    assert "Review product data" in res.text


def test_confirm_requires_auth():
    res = client.post(
        f"/v1/products/{GTIN}/confirm",
        json={
            "name": {"value": "Parle-G", "source": "google:bigbasket", "custom": False},
            "price": {"amount": 10, "currency": "INR", "source": "google:bigbasket", "custom": False},
            "weight": {"value": 250, "unit": "g", "source": "google:bigbasket", "custom": False},
        },
    )
    assert res.status_code == 401


def test_confirm_stores_product_and_bumps_source_confidence():
    res = client.post(
        f"/v1/products/{GTIN}/confirm",
        headers=AUTH,
        json={
            "name": {"value": "Parle-G", "source": "google:bigbasket", "custom": False},
            "price": {"amount": 22, "currency": "INR", "source": "google:flipkart", "custom": False},
            "weight": {"value": 250, "unit": "g", "source": "google:bigbasket", "custom": False},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["gtin"] == GTIN
    assert body["product"]["name"] == "Parle-G"
    assert body["product"]["price"]["amount"] == 22
    assert body["product"]["weight"]["value"] == 250
    assert body["confidence"]["google:bigbasket"] == 2
    assert body["confidence"]["google:flipkart"] == 1


def test_custom_edit_scores_user_not_retailer():
    res = client.post(
        f"/v1/products/{GTIN}/confirm",
        headers=AUTH,
        json={
            "name": {"value": "My custom name", "source": "google:bigbasket", "custom": True},
            "price": {"amount": 47, "currency": "INR", "source": "google:bigbasket", "custom": False},
            "weight": {"value": 19.8, "unit": "g", "source": None, "custom": True},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["product"]["sources"]["name"] == "user"
    assert body["product"]["sources"]["price"] == "google:bigbasket"
    assert body["product"]["sources"]["weight"] == "user"
    assert body["confidence"]["user"] == 2
    assert body["confidence"]["google:bigbasket"] == 1


def test_confirmed_product_is_cache_hit():
    confirm = client.post(
        f"/v1/products/{GTIN}/confirm",
        headers=AUTH,
        json={
            "name": {"value": "Confirmed Parle-G", "source": "google:bigbasket", "custom": False},
            "price": {"amount": 30, "currency": "INR", "source": "google:flipkart", "custom": False},
            "weight": {"value": 250, "unit": "g", "source": "google:bigbasket", "custom": False},
        },
    )
    assert confirm.status_code == 200
    res = client.get(f"/v1/products/{GTIN}", headers=AUTH)
    assert res.status_code == 200
    body = res.json()
    assert body["cache"] == "hit"
    assert body["name"] == ["Confirmed Parle-G"]
    assert body["name_source"] == ["google:bigbasket"]
    assert body["price"][0]["amount"] == 30
    assert body["price_source"] == ["google:flipkart"]
    assert body["weight"][0]["value"] == 250
    assert body["weight_source"] == ["google:bigbasket"]
