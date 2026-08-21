from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from app.extract.bigbasket import extract_bigbasket
from app.extract.google_serp import pick_best_hit
from app.extract.snippet import extract_from_snippet
from app.resolve import product_from_google_item
from app.resolve_samples import _bigbasket_by_path, resolve_from_samples


def test_bigbasket_maggi_fields():
    index = _bigbasket_by_path()
    maggi = index["/pd/266160"]
    extracted = extract_bigbasket(maggi)
    assert extracted["product_name"] == "Maggi 2-Minute Instant Masala Noodles"
    assert extracted["weight"]["value"] == 70
    assert extracted["weight"]["unit"] == "g"
    assert extracted["price"]["currency"] == "INR"
    assert extracted["price"]["amount"] == 13.5
    assert extracted["description"]
    assert "maggi" in extracted["description"].lower()


def test_google_prefers_bigbasket_over_flipkart():
    organic = [
        {
            "title": "Flipkart product",
            "url": "https://www.flipkart.com/parle-g/p/itmfyxnbtgzatmgg",
            "description": "",
            "position": 1,
        },
        {
            "title": "Parle on BigBasket",
            "url": "https://www.bigbasket.com/pd/20004286/parle-glucos-biscuits-parle-g-250-g/",
            "description": "",
            "position": 5,
        },
        {
            "title": "JioMart",
            "url": "https://www.jiomart.com/p/groceries/britannia-bourbon/490000219",
            "description": "",
            "position": 2,
        },
    ]
    best = pick_best_hit(organic)
    assert best is not None
    assert best.source == "bigbasket"


def test_google_falls_to_jiomart_then_amazon():
    organic = [
        {
            "title": "Amazon",
            "url": "https://www.amazon.in/Tata-Salt/dp/B07575FPC3",
            "position": 1,
        },
        {
            "title": "JioMart",
            "url": "https://www.jiomart.com/p/groceries/tata-salt/123",
            "position": 3,
        },
    ]
    best = pick_best_hit(organic)
    assert best is not None
    assert best.source == "jiomart"


def test_snippet_price_and_weight():
    extracted = extract_from_snippet(
        "8901719123870 - PARLE GLUCO BISCUITS 200GM Rate: 29.40 MRP",
        "PARLE GLUCO BISCUITS 200GM Rate : 29.40 MRP : 30.00 EAN / SKU : 8901719123870",
    )
    assert extracted["price"]["amount"] == 29.4
    assert extracted["weight"]["value"] == 200
    assert "Parle" in (extracted["product_name"] or "") or "PARLE" in (extracted["product_name"] or "")


def test_resolve_parle_g_from_saved_samples():
    result = resolve_from_samples("8901719123870")
    assert result.get("error") is None
    assert 1 <= len(result["name"]) <= 3
    assert len(result["name"]) == len(result["name_source"])
    assert result["name"][0]
    assert result["price"][0]["amount"] is not None
    assert result["weight"][0]["unit"] in {"g", "ml"}


def test_bb_index_keys_from_absolute_url():
    index = _bigbasket_by_path()
    assert "/pd/20004286" in index
    parsed = urlparse("https://www.bigbasket.com/pd/20004286/parle-glucos-biscuits-parle-g-250-g/")
    assert parsed.path.rstrip("/") in index or "/pd/20004286" in index


ORBIT_GTIN = "8902433030482"

_ORBIT_BIGBASKET = {
    "title": "Orbit Sweetmint Sugar Free Chewing Gum 19.8 g",
    "websiteTitle": "BigBasket",
    "url": "https://www.bigbasket.com/pc/snacks-branded-foods/mints-chewing-gum/",
    "displayedUrl": "https://www.bigbasket.com › ... › mints & chewing gum",
    "description": (
        "EAN Code: 8902433030482 Marketed by: Mars International India Pvt. Ltd. "
        "Manufactured By: Plot no. is for indicative purposes only."
    ),
    "emphasizedKeywords": ["EAN Code: 8902433030482"],
    "productInfo": {"price": "₹47.00", "rating": 4.1, "numberOfReviews": 447},
    "type": "organic",
    "position": 1,
}


def test_bigbasket_without_pd_path_is_used():
    best = pick_best_hit([_ORBIT_BIGBASKET])
    assert best is not None
    assert best.source == "bigbasket"


def test_orbit_productinfo_price_from_google_serp():
    extracted = extract_from_snippet(
        _ORBIT_BIGBASKET["title"],
        _ORBIT_BIGBASKET["description"],
        product_info=_ORBIT_BIGBASKET["productInfo"],
    )
    assert extracted["product_name"] == "Orbit Sweetmint Sugar Free Chewing Gum 19.8 g"
    assert extracted["price"]["amount"] == 47.0
    assert extracted["price"]["currency"] == "INR"
    assert extracted["weight"]["value"] == 19.8
    assert extracted["weight"]["unit"] == "g"


def test_orbit_resolve_uses_rich_result_not_pdp_scrape():
    result = product_from_google_item(
        ORBIT_GTIN,
        {"organicResults": [_ORBIT_BIGBASKET]},
        cache="miss",
    )
    assert result.get("error") is None
    assert result["name"][0].startswith("Orbit")
    assert result["price"][0]["amount"] == 47.0
    assert result["weight"][0]["value"] == 19.8
    assert result["name_source"][0] == "google:bigbasket"
    assert result["price_source"][0] == "google:bigbasket"
    assert result["weight_source"][0] == "google:bigbasket"


def test_fills_price_from_other_snippet_when_productinfo_empty():
    organic = [
        {
            "title": "Orbit Sweetmint Sugar Free Chewing Gum 19.8 g",
            "url": "https://www.bigbasket.com/pd/40123456/orbit-sweetmint/",
            "description": "EAN Code: 8902433030482 Marketed by: Mars International India Pvt. Ltd.",
            "productInfo": {},
            "position": 1,
        },
        {
            "title": "8902433030482 - ORBIT SWEETMINT 19.8G Rate: 47.00 MRP",
            "url": "https://www.saisupermarket.in/product-detail.php?mid=8902433030482",
            "description": "ORBIT SWEETMINT 19.8GM Rate : 47.00 MRP : 50.00 EAN / SKU : 8902433030482",
            "productInfo": {},
            "position": 2,
        },
    ]
    result = product_from_google_item(ORBIT_GTIN, {"organicResults": organic}, cache="miss")
    assert result["name"][0].startswith("Orbit")
    assert len(result["price"]) == 1
    assert result["price"][0]["amount"] == 47.0
    assert result["price_source"][0] == "google:snippet"
    assert result["weight"][0]["value"] == 19.8
    assert "google:bigbasket" in result["name_source"]


def test_snippet_ignores_delivery_rupee_amount():
    extracted = extract_from_snippet(
        "Orbit Sweetmint Sugar Free Chewing Gum 19.8 g",
        "EAN Code: 8902433030482 ₹21 same-day delivery 7-day returns",
    )
    assert extracted["price"] is None


def test_three_names_and_shorter_price_list():
    organic = [
        {
            "title": "Orbit Sweetmint Sugar Free Chewing Gum 19.8 g",
            "url": "https://www.bigbasket.com/pd/1/orbit/",
            "description": "EAN Code: 8902433030482",
            "productInfo": {},
            "position": 1,
        },
        {
            "title": "Orbit Gum Flipkart Pack",
            "url": "https://www.flipkart.com/orbit/p/abc",
            "description": "EAN 8902433030482 for Rs.50 online Net Quantity 19.8 g",
            "productInfo": {},
            "position": 2,
        },
        {
            "title": "Orbit JioMart Pack",
            "url": "https://www.jiomart.com/p/groceries/orbit/9",
            "description": "8902433030482 Rate: 40",
            "productInfo": {},
            "position": 3,
        },
        {
            "title": "Orbit Amazon Pack",
            "url": "https://www.amazon.in/Orbit/dp/B07575FPC3",
            "description": "8902433030482",
            "productInfo": {},
            "position": 4,
        },
    ]
    result = product_from_google_item(ORBIT_GTIN, {"organicResults": organic}, cache="miss")
    assert len(result["name"]) == 3
    assert result["name_source"][0] == "google:bigbasket"
    assert len(result["price"]) == 2
    assert result["price_source"][0] == "google:jiomart"


def test_higher_confidence_source_listed_first(monkeypatch):
    monkeypatch.setattr(
        "app.resolve.store.all_confidence",
        lambda: {"google:flipkart": 9},
    )
    organic = [
        {
            "title": "Orbit BigBasket",
            "url": "https://www.bigbasket.com/pd/1/orbit/",
            "description": "EAN Code: 8902433030482",
            "productInfo": {"price": "₹47.00"},
            "position": 1,
        },
        {
            "title": "Orbit Flipkart",
            "url": "https://www.flipkart.com/orbit/p/abc",
            "description": "EAN 8902433030482 for Rs.50 online",
            "productInfo": {},
            "position": 2,
        },
    ]
    result = product_from_google_item(ORBIT_GTIN, {"organicResults": organic}, cache="miss")
    assert result["price_source"][0] == "google:flipkart"
    assert result["price"][0]["amount"] == 50.0
    assert result["name_source"][0] == "google:flipkart"
