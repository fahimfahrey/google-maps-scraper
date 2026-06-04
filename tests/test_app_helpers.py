import io
import hashlib
import pandas as pd
import pytest


# Import helpers once app.py defines them.
# These tests will fail until Task 5 writes the app.py helpers.
from app import _adapt_lead, _df_to_csv_bytes, _df_to_excel_bytes


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
