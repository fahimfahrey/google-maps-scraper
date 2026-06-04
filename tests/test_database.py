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


def _seed(gid, name, query=""):
    database.save_lead({
        "google_id": gid, "name": name, "rating": 4.0, "reviews_count": 1,
        "phone": "1", "website": "", "address": "", "category": "",
        "search_query": query,
    })


def test_update_lead_changes_editable_fields():
    _seed("u1", "Old Name")
    database.update_lead("u1", {"name": "New Name", "phone": "999"})
    df = database.fetch_all_leads_as_dataframe()
    row = df[df["google_id"] == "u1"].iloc[0]
    assert row["name"] == "New Name"
    assert row["phone"] == "999"


def test_update_lead_ignores_unknown_columns():
    _seed("u2", "Keep")
    database.update_lead("u2", {"google_id": "hacked", "id": 999, "nope": "x"})
    df = database.fetch_all_leads_as_dataframe()
    assert "hacked" not in df["google_id"].tolist()
    assert (df["google_id"] == "u2").any()


def test_delete_lead_removes_single_row():
    _seed("d1", "A")
    _seed("d2", "B")
    database.delete_lead("d1")
    ids = database.fetch_all_leads_as_dataframe()["google_id"].tolist()
    assert ids == ["d2"]


def test_delete_by_query_removes_matching_group():
    _seed("q1", "A", "coffee")
    _seed("q2", "B", "coffee")
    _seed("q3", "C", "plumbers")
    removed = database.delete_by_query("coffee")
    assert removed == 2
    assert database.count_leads() == 1


def test_delete_by_query_unlabeled_matches_empty_query():
    _seed("n1", "A", "")  # legacy/empty → 'Unlabeled'
    database.delete_by_query("Unlabeled")
    assert database.count_leads() == 0


def test_delete_all_empties_table():
    _seed("a1", "A")
    _seed("a2", "B")
    database.delete_all()
    assert database.count_leads() == 0
