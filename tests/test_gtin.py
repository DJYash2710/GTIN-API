from app.gtin import is_valid_gtin, normalize_gtin


def test_parle_g_gtin_valid():
    assert is_valid_gtin("8901719123870")


def test_rejects_short_or_letters():
    assert not is_valid_gtin("123")
    assert not is_valid_gtin("abc")


def test_normalize_strips_spaces():
    assert normalize_gtin(" 8901719123870 ") == "8901719123870"
