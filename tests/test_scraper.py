"""Tests for scraper module."""

import pytest
from unittest.mock import MagicMock, patch, call
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

import scraper


class TestBuildContext:
    """Tests for _build_context helper."""

    def test_build_context_sets_user_agent(self):
        """Assert user_agent and viewport are set correctly."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        result = scraper._build_context(mock_browser)

        mock_browser.new_context.assert_called_once_with(
            user_agent=scraper._USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )
        assert result is mock_context

    def test_build_context_calls_stealth_sync(self):
        """Assert Stealth().apply_stealth_sync is called with the context."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        with patch("scraper.Stealth") as MockStealth:
            mock_stealth_instance = MagicMock()
            MockStealth.return_value = mock_stealth_instance
            scraper._build_context(mock_browser)
            mock_stealth_instance.apply_stealth_sync.assert_called_once_with(
                mock_context
            )

    def test_user_agent_is_realistic_chrome(self):
        """Assert _USER_AGENT contains Chrome/124 and no HeadlessChrome."""
        assert "Chrome/124" in scraper._USER_AGENT
        assert "HeadlessChrome" not in scraper._USER_AGENT


class TestDismissConsent:
    """Tests for _dismiss_consent helper."""

    def test_dismiss_consent_clicks_button_when_present(self):
        """Assert consent button is clicked and networkidle is awaited."""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_page.locator.return_value = mock_locator

        scraper._dismiss_consent(mock_page)

        # Verify locator was called with combined selector
        call_args = mock_page.locator.call_args[0][0]
        assert 'Accept all' in call_args
        assert 'Alle akzeptieren' in call_args

        mock_locator.first.click.assert_called_once_with(
            timeout=scraper._CONSENT_TIMEOUT_MS
        )
        mock_page.wait_for_load_state.assert_called_once_with("networkidle")

    def test_dismiss_consent_silent_on_timeout(self):
        """Assert no exception propagates when click times out."""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.first.click.side_effect = PlaywrightTimeoutError("timeout")

        # Should not raise
        scraper._dismiss_consent(mock_page)

        # wait_for_load_state should not be called if click failed
        mock_page.wait_for_load_state.assert_not_called()

    def test_consent_texts_include_localizations(self):
        """Assert consent texts cover multiple languages."""
        assert "Accept all" in scraper._CONSENT_TEXTS
        assert "Alle akzeptieren" in scraper._CONSENT_TEXTS
        assert "Tout accepter" in scraper._CONSENT_TEXTS
        assert "Aceitar tudo" in scraper._CONSENT_TEXTS


class TestBlockMedia:
    """Tests for _block_media helper."""

    def test_block_media_registers_route(self):
        """Assert media route is registered for abort."""
        mock_page = MagicMock()

        scraper._block_media(mock_page)

        mock_page.route.assert_called_once()
        pattern, handler = mock_page.route.call_args[0]
        assert "**/*." in pattern
        assert "png" in pattern or "jpg" in pattern


class TestScrape:
    """Tests for main scrape function."""

    @patch("scraper.sync_playwright")
    def test_scrape_returns_empty_list(self, mock_sync_playwright):
        """Assert scrape returns empty list."""
        # Setup the mock context manager chain
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None

        mock_browser.new_context.return_value.__enter__.return_value = mock_context
        mock_browser.new_context.return_value.__exit__.return_value = None

        mock_context.new_page.return_value = mock_page

        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        mock_sync_playwright.return_value.__exit__.return_value = None

        with patch("scraper._build_context", return_value=mock_context):
            with patch("scraper._dismiss_consent"):
                result = scraper.scrape("unused")

        assert result == []

    @patch("scraper.sync_playwright")
    def test_scrape_navigates_to_maps_url(self, mock_sync_playwright):
        """Assert scrape navigates to _MAPS_URL."""
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        # Setup context manager chain
        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_context.__enter__.return_value = mock_context
        mock_context.__exit__.return_value = None
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context

        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        mock_sync_playwright.return_value.__exit__.return_value = None

        with patch("scraper._dismiss_consent"):
            scraper.scrape("unused")

        mock_page.goto.assert_called_once_with(
            scraper._MAPS_URL, wait_until="networkidle"
        )

    @patch("scraper.sync_playwright")
    def test_scrape_calls_dismiss_consent(self, mock_sync_playwright):
        """Assert scrape calls _dismiss_consent with page."""
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        # Setup context manager chain
        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_context.__enter__.return_value = mock_context
        mock_context.__exit__.return_value = None
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context

        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        mock_sync_playwright.return_value.__exit__.return_value = None

        with patch("scraper._dismiss_consent") as mock_dismiss:
            scraper.scrape("unused")
            mock_dismiss.assert_called_once_with(mock_page)

    @patch("scraper.sync_playwright")
    def test_scrape_calls_block_media_before_goto(self, mock_sync_playwright):
        """Assert _block_media is called before page.goto."""
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        # Setup context manager chain
        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_context.__enter__.return_value = mock_context
        mock_context.__exit__.return_value = None
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context

        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        mock_sync_playwright.return_value.__exit__.return_value = None

        call_order = []
        mock_page.route.side_effect = lambda *args, **kwargs: call_order.append(
            "route"
        )
        mock_page.goto.side_effect = lambda *args, **kwargs: call_order.append("goto")

        with patch("scraper._dismiss_consent"):
            scraper.scrape("unused")

        # route (block_media) should be called before goto
        assert call_order.index("route") < call_order.index("goto")

    @patch("scraper.sync_playwright")
    def test_scrape_uses_launch_args(self, mock_sync_playwright):
        """Assert scrape passes _LAUNCH_ARGS to chromium.launch."""
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_browser.new_context.return_value.__enter__.return_value = mock_context
        mock_browser.new_context.return_value.__exit__.return_value = None
        mock_context.new_page.return_value = mock_page

        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        mock_sync_playwright.return_value.__exit__.return_value = None

        with patch("scraper._build_context", return_value=mock_context):
            with patch("scraper._dismiss_consent"):
                scraper.scrape("unused")

        mock_p.chromium.launch.assert_called_once()
        launch_kwargs = mock_p.chromium.launch.call_args[1]
        assert launch_kwargs["args"] == scraper._LAUNCH_ARGS
        assert launch_kwargs["headless"] is True

    def test_launch_args_disable_sandbox(self):
        """Assert _LAUNCH_ARGS disables sandbox for container environments."""
        assert "--no-sandbox" in scraper._LAUNCH_ARGS
        assert "--disable-setuid-sandbox" in scraper._LAUNCH_ARGS
        assert "--disable-dev-shm-usage" in scraper._LAUNCH_ARGS


class TestScrollConstants:
    """Tests for scroll-related module constants."""

    def test_scroll_step_is_2000(self):
        assert scraper._SCROLL_STEP_PX == 2_000

    def test_jitter_range_valid(self):
        assert scraper._SCROLL_JITTER_MIN == 1.5
        assert scraper._SCROLL_JITTER_MAX == 3.5
        assert scraper._SCROLL_JITTER_MIN < scraper._SCROLL_JITTER_MAX

    def test_stale_limit_is_3(self):
        assert scraper._SCROLL_STALE_LIMIT == 3

    def test_feed_selectors_includes_role_feed(self):
        assert 'div[role="feed"]' in scraper._FEED_SELECTORS

    def test_feed_selectors_includes_aria_label_fallback(self):
        assert any("aria-label" in s for s in scraper._FEED_SELECTORS)

    def test_end_of_list_text_matches_maps_message(self):
        assert scraper._END_OF_LIST_TEXT == "You've reached the end of the list"


class TestLocateFeed:
    """Tests for _locate_feed helper."""

    def test_locate_feed_returns_first_match_on_primary_selector(self):
        """Primary selector div[role='feed'] resolves when count > 0."""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_page.locator.return_value = mock_locator

        result = scraper._locate_feed(mock_page)

        mock_page.locator.assert_called_with('div[role="feed"]')
        assert result is mock_locator.first

    def test_locate_feed_falls_back_to_aria_label_selector(self):
        """When primary selector has count 0, tries aria-label fallback."""
        mock_page = MagicMock()

        primary_locator = MagicMock()
        primary_locator.count.return_value = 0

        fallback_locator = MagicMock()
        fallback_locator.count.return_value = 1

        mock_page.locator.side_effect = [primary_locator, fallback_locator]

        result = scraper._locate_feed(mock_page)

        assert mock_page.locator.call_count == 2
        assert result is fallback_locator.first

    def test_locate_feed_raises_when_no_selector_matches(self):
        """RuntimeError raised when all selectors return count 0."""
        mock_page = MagicMock()
        empty_locator = MagicMock()
        empty_locator.count.return_value = 0
        mock_page.locator.return_value = empty_locator

        with pytest.raises(RuntimeError, match="Maps feed container not found"):
            scraper._locate_feed(mock_page)
