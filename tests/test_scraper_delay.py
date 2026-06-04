from unittest.mock import patch, MagicMock
import scraper


def _make_mock_pw():
    mock_pw = MagicMock()
    mock_browser = MagicMock()
    mock_pw.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw.__exit__ = MagicMock(return_value=False)
    mock_pw.chromium.launch.return_value.__enter__ = MagicMock(return_value=mock_browser)
    mock_pw.chromium.launch.return_value.__exit__ = MagicMock(return_value=False)
    return mock_pw, mock_browser


@patch("scraper.sync_playwright")
@patch("scraper._scrape_one_url", return_value=[])
@patch("scraper.time")
def test_delay_preset_slow_uses_wider_range(mock_time, mock_scrape, mock_pw):
    mock_pw.return_value = _make_mock_pw()[0]
    scraper.scrape_multi(["q1", "q2"], delay_preset="slow")
    call_args = mock_time.sleep.call_args[0][0]
    assert 15.0 <= call_args <= 30.0


@patch("scraper.sync_playwright")
@patch("scraper._scrape_one_url", return_value=[])
@patch("scraper.time")
def test_delay_preset_fast_uses_shorter_range(mock_time, mock_scrape, mock_pw):
    mock_pw.return_value = _make_mock_pw()[0]
    scraper.scrape_multi(["q1", "q2"], delay_preset="fast")
    call_args = mock_time.sleep.call_args[0][0]
    assert 1.5 <= call_args <= 5.0


@patch("scraper.sync_playwright")
@patch("scraper._scrape_one_url", return_value=[])
@patch("scraper.time")
def test_delay_preset_normal_is_default(mock_time, mock_scrape, mock_pw):
    mock_pw.return_value = _make_mock_pw()[0]
    scraper.scrape_multi(["q1", "q2"])
    call_args = mock_time.sleep.call_args[0][0]
    assert 5.0 <= call_args <= 15.0


@patch("scraper.sync_playwright")
@patch("scraper._scrape_one_url", return_value=[])
@patch("scraper.time")
def test_delay_preset_unknown_falls_back_to_normal(mock_time, mock_scrape, mock_pw):
    mock_pw.return_value = _make_mock_pw()[0]
    scraper.scrape_multi(["q1", "q2"], delay_preset="turbo")
    call_args = mock_time.sleep.call_args[0][0]
    assert 5.0 <= call_args <= 15.0
