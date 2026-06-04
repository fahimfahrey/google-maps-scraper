"""Tests for row_callback / log_callback params added to scrape_multi."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

import scraper


class TestRowCallback:
    @patch("scraper.sync_playwright")
    @patch("scraper._scrape_one_url")
    def test_row_callback_called_for_each_unique_result(self, mock_one, mock_pw):
        mock_pw.return_value.__enter__ = MagicMock(return_value=mock_pw.return_value)
        mock_pw.return_value.__exit__ = MagicMock(return_value=False)
        browser_ctx = MagicMock()
        browser_ctx.__enter__ = MagicMock(return_value=MagicMock())
        browser_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value.chromium.launch.return_value = browser_ctx

        mock_one.return_value = [
            {"name": "A", "phone": "1", "rating": "", "reviews": "", "website": ""},
            {"name": "B", "phone": "2", "rating": "", "reviews": "", "website": ""},
        ]

        collected = []
        scraper.scrape_multi(["q1"], row_callback=collected.append)
        assert len(collected) == 2
        assert collected[0]["name"] == "A"
        assert collected[1]["name"] == "B"

    @patch("scraper.sync_playwright")
    @patch("scraper._scrape_one_url")
    def test_row_callback_not_called_for_duplicate(self, mock_one, mock_pw):
        mock_pw.return_value.__enter__ = MagicMock(return_value=mock_pw.return_value)
        mock_pw.return_value.__exit__ = MagicMock(return_value=False)
        browser_ctx = MagicMock()
        browser_ctx.__enter__ = MagicMock(return_value=MagicMock())
        browser_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value.chromium.launch.return_value = browser_ctx

        dup = {"name": "A", "phone": "1", "rating": "", "reviews": "", "website": ""}
        mock_one.side_effect = [[dup], [dup]]

        collected = []
        scraper.scrape_multi(["q1", "q2"], row_callback=collected.append)
        assert len(collected) == 1  # second occurrence dropped by dedup

    @patch("scraper.sync_playwright")
    @patch("scraper._scrape_one_url")
    def test_row_callback_none_does_not_raise(self, mock_one, mock_pw):
        mock_pw.return_value.__enter__ = MagicMock(return_value=mock_pw.return_value)
        mock_pw.return_value.__exit__ = MagicMock(return_value=False)
        browser_ctx = MagicMock()
        browser_ctx.__enter__ = MagicMock(return_value=MagicMock())
        browser_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value.chromium.launch.return_value = browser_ctx

        mock_one.return_value = [{"name": "X", "phone": "0", "rating": "", "reviews": "", "website": ""}]
        # No row_callback arg → backward compat
        result = scraper.scrape_multi(["q1"])
        assert result[0]["name"] == "X"

    @patch("scraper.sync_playwright")
    @patch("scraper._scrape_one_url")
    def test_return_value_unchanged_when_callback_provided(self, mock_one, mock_pw):
        mock_pw.return_value.__enter__ = MagicMock(return_value=mock_pw.return_value)
        mock_pw.return_value.__exit__ = MagicMock(return_value=False)
        browser_ctx = MagicMock()
        browser_ctx.__enter__ = MagicMock(return_value=MagicMock())
        browser_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value.chromium.launch.return_value = browser_ctx

        mock_one.return_value = [{"name": "Y", "phone": "9", "rating": "", "reviews": "", "website": ""}]
        result = scraper.scrape_multi(["q1"], row_callback=lambda r: None)
        assert result == [{"name": "Y", "phone": "9", "rating": "", "reviews": "", "website": ""}]


class TestLogCallback:
    @patch("scraper.sync_playwright")
    @patch("scraper._scrape_one_url")
    def test_log_callback_called_once_per_query(self, mock_one, mock_pw):
        mock_pw.return_value.__enter__ = MagicMock(return_value=mock_pw.return_value)
        mock_pw.return_value.__exit__ = MagicMock(return_value=False)
        browser_ctx = MagicMock()
        browser_ctx.__enter__ = MagicMock(return_value=MagicMock())
        browser_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value.chromium.launch.return_value = browser_ctx

        mock_one.return_value = []
        logs = []
        scraper.scrape_multi(["q1", "q2", "q3"], log_callback=logs.append)
        assert len(logs) == 3

    @patch("scraper.sync_playwright")
    @patch("scraper._scrape_one_url")
    def test_log_callback_text_contains_query_name(self, mock_one, mock_pw):
        mock_pw.return_value.__enter__ = MagicMock(return_value=mock_pw.return_value)
        mock_pw.return_value.__exit__ = MagicMock(return_value=False)
        browser_ctx = MagicMock()
        browser_ctx.__enter__ = MagicMock(return_value=MagicMock())
        browser_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value.chromium.launch.return_value = browser_ctx

        mock_one.return_value = []
        logs = []
        scraper.scrape_multi(["coffee london"], log_callback=logs.append)
        assert "coffee london" in logs[0]

    @patch("scraper.sync_playwright")
    @patch("scraper._scrape_one_url")
    def test_log_callback_none_does_not_raise(self, mock_one, mock_pw):
        mock_pw.return_value.__enter__ = MagicMock(return_value=mock_pw.return_value)
        mock_pw.return_value.__exit__ = MagicMock(return_value=False)
        browser_ctx = MagicMock()
        browser_ctx.__enter__ = MagicMock(return_value=MagicMock())
        browser_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value.chromium.launch.return_value = browser_ctx

        mock_one.return_value = []
        scraper.scrape_multi(["q1"])  # no log_callback → no error

    @patch("scraper.sync_playwright")
    @patch("scraper._scrape_one_url")
    def test_log_callback_includes_position_counter(self, mock_one, mock_pw):
        mock_pw.return_value.__enter__ = MagicMock(return_value=mock_pw.return_value)
        mock_pw.return_value.__exit__ = MagicMock(return_value=False)
        browser_ctx = MagicMock()
        browser_ctx.__enter__ = MagicMock(return_value=MagicMock())
        browser_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw.return_value.chromium.launch.return_value = browser_ctx

        mock_one.return_value = []
        logs = []
        scraper.scrape_multi(["a", "b"], log_callback=logs.append)
        assert "1/2" in logs[0]
        assert "2/2" in logs[1]
