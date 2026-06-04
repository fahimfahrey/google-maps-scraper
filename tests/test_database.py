import os
import pytest
import database


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.initialize_db()


def test_count_leads_returns_zero_on_empty_db():
    assert database.count_leads() == 0


def test_count_leads_returns_correct_count_after_inserts():
    database.save_lead({
        "google_id": "a1", "name": "Cafe A", "rating": 4.5,
        "reviews_count": 10, "phone": "111", "website": "", "address": "", "category": "",
    })
    database.save_lead({
        "google_id": "b2", "name": "Cafe B", "rating": 3.0,
        "reviews_count": 5, "phone": "222", "website": "", "address": "", "category": "",
    })
    assert database.count_leads() == 2


def test_count_leads_ignores_duplicates():
    database.save_lead({
        "google_id": "dup1", "name": "X", "rating": 0.0,
        "reviews_count": 0, "phone": "", "website": "", "address": "", "category": "",
    })
    database.save_lead({
        "google_id": "dup1", "name": "X", "rating": 0.0,
        "reviews_count": 0, "phone": "", "website": "", "address": "", "category": "",
    })
    assert database.count_leads() == 1
