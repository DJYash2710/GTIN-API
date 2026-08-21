"""Keep pytest on samples only. Never spend Apify credits in tests."""

import os

import pytest

os.environ["APIFY_ENABLED"] = "false"
os.environ.setdefault("API_KEY", "dev-local-key")


@pytest.fixture(autouse=True)
def _isolated_master_db(monkeypatch):
    monkeypatch.delenv("MYSQL_HOST", raising=False)
    monkeypatch.delenv("MASTER_DB", raising=False)
    from app import store

    store.reset_connection()
    yield
    store.reset_connection()

