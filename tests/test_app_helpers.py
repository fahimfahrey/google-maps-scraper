import io
import hashlib
import pandas as pd
import pytest


# Import helpers once app.py defines them.
# These tests will fail until Task 5 writes the app.py helpers.
from app import _adapt_lead, _df_to_csv_bytes, _df_to_excel_bytes, _apply_editor_changes
import database


class TestAdaptLead:
    def test_generates_google_id_from_name_and_phone(self):
        record = {"name": "Café X", "phone": "+1-800-555-0100", "rating": "4.5",
                  "reviews": "120", "website": "https://ex.com"}
        result = _adapt_lead(record)
        expected_key = "Café X|+1-800-555-0100"
        assert result["google_id"] == hashlib.md5(expected_key.encode()).hexdigest()

    def test_maps_reviews_to_reviews_count(self):
        record = {"name": "A", "phone": "", "reviews": "42", "rating": "", "website": ""}
        assert _adapt_lead(record)["reviews_count"] == "42"

    def test_address_and_category_are_empty(self):
        record = {"name": "B", "phone": "", "reviews": "", "rating": "", "website": ""}
        result = _adapt_lead(record)
        assert result["address"] == ""
        assert result["category"] == ""

    def test_missing_fields_default_to_empty_string(self):
        result = _adapt_lead({})
        assert result["name"] == ""
        assert result["phone"] == ""
        assert result["rating"] == ""

    def test_google_id_deterministic_for_same_input(self):
        record = {"name": "Z", "phone": "000", "reviews": "", "rating": "", "website": ""}
        assert _adapt_lead(record)["google_id"] == _adapt_lead(record)["google_id"]


class TestDfToCsvBytes:
    def _sample_df(self):
        return pd.DataFrame({"name": ["A", "B"], "rating": [4.0, 3.5]})

    def test_returns_bytes(self):
        assert isinstance(_df_to_csv_bytes(self._sample_df()), bytes)

    def test_csv_contains_header(self):
        result = _df_to_csv_bytes(self._sample_df()).decode("utf-8")
        assert "name" in result
        assert "rating" in result

    def test_csv_contains_data_rows(self):
        result = _df_to_csv_bytes(self._sample_df()).decode("utf-8")
        assert "A" in result
        assert "4.0" in result


class TestDfToExcelBytes:
    def _sample_df(self):
        return pd.DataFrame({"name": ["A"], "phone": ["123"]})

    def test_returns_bytes(self):
        assert isinstance(_df_to_excel_bytes(self._sample_df()), bytes)

    def test_bytes_start_with_xlsx_magic(self):
        data = _df_to_excel_bytes(self._sample_df())
        # xlsx files start with PK (zip magic: 0x50 0x4B)
        assert data[:2] == b"PK"

    def test_roundtrip_preserves_columns(self):
        df = self._sample_df()
        data = _df_to_excel_bytes(df)
        buf = io.BytesIO(data)
        result = pd.read_excel(buf)
        assert list(result.columns) == list(df.columns)


class TestApplyEditorChanges:
    @pytest.fixture(autouse=True)
    def tmp_db(self, tmp_path, monkeypatch):
        monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "edit.db"))
        database.initialize_db()
        for gid, name in [("e1", "Alpha"), ("e2", "Beta"), ("e3", "Gamma")]:
            database.save_lead({"google_id": gid, "name": name, "rating": 4.0,
                                "reviews_count": 1, "phone": "1", "website": "",
                                "address": "", "category": "", "search_query": "q"})

    def _df(self):
        return database.fetch_all_leads_as_dataframe().reset_index(drop=True)

    def test_edit_persists(self):
        df = self._df()
        changed = _apply_editor_changes(df, {"edited_rows": {0: {"name": "Renamed"}}}, None)
        assert changed
        row = database.fetch_all_leads_as_dataframe()
        assert "Renamed" in row["name"].tolist()

    def test_delete_persists(self):
        df = self._df()
        _apply_editor_changes(df, {"deleted_rows": [1]}, None)
        names = database.fetch_all_leads_as_dataframe()["name"].tolist()
        assert "Beta" not in names and len(names) == 2

    def test_added_row_inherits_query_label(self):
        df = self._df()
        _apply_editor_changes(df, {"added_rows": [{"name": "NewBiz", "phone": "55"}]}, "plumbers")
        added = database.fetch_all_leads_as_dataframe()
        new = added[added["name"] == "NewBiz"].iloc[0]
        assert new["search_query"] == "plumbers"

    def test_added_row_without_name_skipped(self):
        df = self._df()
        changed = _apply_editor_changes(df, {"added_rows": [{"phone": "x"}]}, "q")
        assert not changed
        assert database.count_leads() == 3

    def test_no_changes_returns_false(self):
        df = self._df()
        assert _apply_editor_changes(df, {}, None) is False
