from app.apify_google import google_run_input


def test_google_query_is_gtin_only_without_inurl_or_site():
    payload = google_run_input("8902433030482")
    assert payload["queries"] == "8902433030482"
    assert "site:" not in payload["queries"]
    assert "inurl:" not in payload["queries"]
    assert "site" not in payload
    assert "relatedToSite" not in payload
    assert "wordsInUrl" not in payload
    assert "wordsInTitle" not in payload
    assert "wordsInText" not in payload
    assert "websiteContentScraper" not in payload
    assert payload["countryCode"] == "in"
    assert payload["maxPagesPerQuery"] == 1
    assert payload["mobileResults"] is False
    assert payload["focusOnPaidAds"] is False
