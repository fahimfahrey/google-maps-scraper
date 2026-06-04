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
            with patch("scraper._dismiss_consent"), \
                 patch("scraper._scroll_feed"):
                result = scraper.scrape("unused")

        assert result == []

    @patch("scraper.sync_playwright")
    def test_scrape_navigates_to_maps_url(self, mock_sync_playwright):
        """Assert scrape navigates to the supplied url."""
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

        test_url = "https://www.google.com/maps/search/test"
        with patch("scraper._dismiss_consent"), \
             patch("scraper._scroll_feed"):
            scraper.scrape(test_url)

        mock_page.goto.assert_called_once_with(test_url, wait_until="networkidle")

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

        with patch("scraper._dismiss_consent") as mock_dismiss, \
             patch("scraper._scroll_feed"):
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

        with patch("scraper._dismiss_consent"), \
             patch("scraper._scroll_feed"):
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
            with patch("scraper._dismiss_consent"), \
                 patch("scraper._scroll_feed"):
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


class TestEndOfListVisible:
    """Tests for _end_of_list_visible helper."""

    def test_returns_true_when_text_present(self):
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_page.locator.return_value = mock_locator

        assert scraper._end_of_list_visible(mock_page) is True

    def test_returns_false_when_text_absent(self):
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_page.locator.return_value = mock_locator

        assert scraper._end_of_list_visible(mock_page) is False

    def test_uses_end_of_list_text_constant(self):
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_page.locator.return_value = mock_locator

        scraper._end_of_list_visible(mock_page)

        call_selector = mock_page.locator.call_args[0][0]
        assert scraper._END_OF_LIST_TEXT in call_selector


class TestScrollFeed:
    """Tests for _scroll_feed helper."""

    def _make_page_mock(self, heights, end_of_list_counts=None):
        """Build a mock page that returns sequential scrollHeight values.

        heights: list of ints returned by page.evaluate on successive calls.
        end_of_list_counts: list of ints for _end_of_list_visible locator.count().
                            Defaults to all-0 (never reached end).
        """
        mock_page = MagicMock()

        if end_of_list_counts is None:
            end_of_list_counts = [0] * (len(heights) + 5)

        eol_iter = iter(end_of_list_counts)

        def locator_side_effect(selector):
            loc = MagicMock()
            if scraper._END_OF_LIST_TEXT in selector:
                loc.count.side_effect = lambda: next(eol_iter, 0)
            else:
                loc.count.return_value = 1
                loc.first.element_handle.return_value = MagicMock()
            return loc

        mock_page.locator.side_effect = locator_side_effect

        height_iter = iter(heights)
        mock_page.evaluate.side_effect = lambda js, *args: next(height_iter, heights[-1])

        return mock_page

    def test_scroll_feed_breaks_on_end_of_list(self):
        """Stops immediately when end-of-list notice is present on first check."""
        mock_page = MagicMock()

        eol_loc = MagicMock()
        eol_loc.count.return_value = 1

        feed_loc = MagicMock()
        feed_loc.count.return_value = 1
        feed_handle = MagicMock()
        feed_loc.first.element_handle.return_value = feed_handle

        def locator_side_effect(selector):
            if scraper._END_OF_LIST_TEXT in selector:
                return eol_loc
            return feed_loc

        mock_page.locator.side_effect = locator_side_effect

        with patch("scraper.time") as mock_time, \
             patch("scraper._locate_feed", return_value=feed_loc.first):
            feed_loc.first.element_handle.return_value = feed_handle
            scraper._scroll_feed(mock_page)

        mock_page.evaluate.assert_not_called()
        mock_time.sleep.assert_not_called()

    def test_scroll_feed_breaks_after_three_stale_scrolls(self):
        """Stops after _SCROLL_STALE_LIMIT consecutive scrolls with no height change."""
        mock_page = MagicMock()
        feed_handle = MagicMock()
        mock_feed_locator = MagicMock()
        mock_feed_locator.element_handle.return_value = feed_handle

        eol_loc = MagicMock()
        eol_loc.count.return_value = 0
        mock_page.locator.return_value = eol_loc

        # scrollHeight stays at 3000 on every call — always stale
        mock_page.evaluate.return_value = 3_000

        with patch("scraper.time") as mock_time, \
             patch("scraper.random.uniform", return_value=2.0), \
             patch("scraper._locate_feed", return_value=mock_feed_locator), \
             patch("scraper._end_of_list_visible", return_value=False):
            scraper._scroll_feed(mock_page)

        assert mock_time.sleep.call_count == scraper._SCROLL_STALE_LIMIT + 1

    def test_scroll_feed_resets_stale_count_on_height_increase(self):
        """Stale counter resets when scrollHeight grows."""
        mock_page = MagicMock()
        feed_handle = MagicMock()
        mock_feed_locator = MagicMock()
        mock_feed_locator.element_handle.return_value = feed_handle

        # heights: grows twice, then stays (3 stale)
        # Iteration 1: evaluate → 3000 (grew from 0) stale=0
        # Iteration 2: evaluate → 6000 (grew) stale=0
        # Iteration 3: evaluate → 6000 (stale) stale=1
        # Iteration 4: evaluate → 6000 (stale) stale=2
        # Iteration 5: evaluate → 6000 (stale) stale=3 → break
        heights = iter([3_000, 6_000, 6_000, 6_000, 6_000])
        mock_page.evaluate.side_effect = lambda js, *args: next(heights, 6_000)

        with patch("scraper.time"), \
             patch("scraper.random.uniform", return_value=2.0), \
             patch("scraper._locate_feed", return_value=mock_feed_locator), \
             patch("scraper._end_of_list_visible", return_value=False):
            scraper._scroll_feed(mock_page)

        assert mock_page.evaluate.call_count == 5

    def test_scroll_feed_uses_scroll_step_constant(self):
        """Evaluate call passes _SCROLL_STEP_PX in arguments."""
        mock_page = MagicMock()
        feed_handle = MagicMock()
        mock_feed_locator = MagicMock()
        mock_feed_locator.element_handle.return_value = feed_handle

        mock_page.evaluate.return_value = 0

        with patch("scraper.time"), \
             patch("scraper.random.uniform", return_value=2.0), \
             patch("scraper._locate_feed", return_value=mock_feed_locator), \
             patch("scraper._end_of_list_visible", return_value=False):
            scraper._scroll_feed(mock_page)

        for call in mock_page.evaluate.call_args_list:
            args = call[0][1] if len(call[0]) > 1 else []
            if scraper._SCROLL_STEP_PX in args:
                return
        assert False, f"_SCROLL_STEP_PX not found in evaluate args"

    def test_scroll_feed_sleep_uses_random_jitter(self):
        """time.sleep is called with result of random.uniform(jitter_min, jitter_max)."""
        mock_page = MagicMock()
        feed_handle = MagicMock()
        mock_feed_locator = MagicMock()
        mock_feed_locator.element_handle.return_value = feed_handle

        mock_page.evaluate.return_value = 0

        with patch("scraper.time") as mock_time, \
             patch("scraper.random.uniform", return_value=2.75) as mock_uniform, \
             patch("scraper._locate_feed", return_value=mock_feed_locator), \
             patch("scraper._end_of_list_visible", return_value=False):
            scraper._scroll_feed(mock_page)

        mock_uniform.assert_called_with(
            scraper._SCROLL_JITTER_MIN, scraper._SCROLL_JITTER_MAX
        )
        mock_time.sleep.assert_called_with(2.75)

    def test_scroll_feed_calls_locate_feed_once(self):
        """_locate_feed called exactly once — element handle cached for loop."""
        mock_page = MagicMock()
        feed_handle = MagicMock()
        mock_feed_locator = MagicMock()
        mock_feed_locator.element_handle.return_value = feed_handle

        mock_page.evaluate.return_value = 0

        with patch("scraper.time"), \
             patch("scraper.random.uniform", return_value=2.0), \
             patch("scraper._locate_feed", return_value=mock_feed_locator) as mock_locate, \
             patch("scraper._end_of_list_visible", return_value=False):
            scraper._scroll_feed(mock_page)

        mock_locate.assert_called_once_with(mock_page)


class TestScrapeScrollIntegration:
    """Tests that scrape() wires _scroll_feed after navigation."""

    @patch("scraper.sync_playwright")
    def test_scrape_calls_scroll_feed_with_page(self, mock_sync_playwright):
        """scrape() calls _scroll_feed(page) after navigation."""
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_context.__enter__.return_value = mock_context
        mock_context.__exit__.return_value = None
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        mock_sync_playwright.return_value.__exit__.return_value = None

        with patch("scraper._dismiss_consent"), \
             patch("scraper._scroll_feed") as mock_scroll:
            scraper.scrape("https://www.google.com/maps/search/coffee+shops")

        mock_scroll.assert_called_once_with(mock_page)

    @patch("scraper.sync_playwright")
    def test_scrape_navigates_to_supplied_url(self, mock_sync_playwright):
        """scrape() navigates to the caller-supplied url, not _MAPS_URL."""
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_context.__enter__.return_value = mock_context
        mock_context.__exit__.return_value = None
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        mock_sync_playwright.return_value.__exit__.return_value = None

        test_url = "https://www.google.com/maps/search/gyms+near+london"

        with patch("scraper._dismiss_consent"), \
             patch("scraper._scroll_feed"):
            scraper.scrape(test_url)

        mock_page.goto.assert_called_once_with(test_url, wait_until="networkidle")

    @patch("scraper.sync_playwright")
    def test_scrape_scroll_called_after_consent(self, mock_sync_playwright):
        """_scroll_feed is called after _dismiss_consent, not before."""
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_context.__enter__.return_value = mock_context
        mock_context.__exit__.return_value = None
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        mock_sync_playwright.return_value.__exit__.return_value = None

        call_order = []

        with patch("scraper._dismiss_consent",
                   side_effect=lambda *a: call_order.append("consent")), \
             patch("scraper._scroll_feed",
                   side_effect=lambda *a: call_order.append("scroll")):
            scraper.scrape("https://www.google.com/maps/search/test")

        assert call_order.index("consent") < call_order.index("scroll")


class TestParsingConstants:
    """Tests for parsing-layer module constants."""

    def test_phone_regex_is_compiled_pattern(self):
        import re as _re
        assert isinstance(scraper._PHONE_REGEX, _re.Pattern)

    def test_phone_regex_matches_international_format(self):
        assert scraper._PHONE_REGEX.search('+44 20 7946 0958')

    def test_phone_regex_matches_nanp_format(self):
        assert scraper._PHONE_REGEX.search('(555) 123-4567')

    def test_phone_regex_matches_uk_local_format(self):
        assert scraper._PHONE_REGEX.search('01234 567890')

    def test_phone_regex_does_not_match_short_number(self):
        assert not scraper._PHONE_REGEX.search('123')

    def test_place_link_selector_targets_maps_place_path(self):
        assert '/maps/place/' in scraper._PLACE_LINK_SELECTOR

    def test_website_item_id_is_authority(self):
        assert scraper._WEBSITE_ITEM_ID == 'authority'

    def test_phone_item_id_fragment_is_phone(self):
        assert scraper._PHONE_ITEM_ID == 'phone'


class TestExtractName:
    """Tests for _extract_name helper."""

    def _make_soup(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'lxml')

    def test_extracts_name_from_aria_label_on_place_link(self):
        soup = self._make_soup(
            '<a href="/maps/place/Coffee+House" aria-label="Coffee House">Coffee House</a>'
        )
        assert scraper._extract_name(soup) == 'Coffee House'

    def test_falls_back_to_role_heading_when_no_aria_label(self):
        soup = self._make_soup(
            '<a href="/maps/place/Bakery"></a>'
            '<div role="heading">The Bakery</div>'
        )
        assert scraper._extract_name(soup) == 'The Bakery'

    def test_returns_empty_string_when_no_name_found(self):
        soup = self._make_soup('<div>no name here</div>')
        assert scraper._extract_name(soup) == ''

    def test_returns_empty_string_on_none_soup(self):
        assert scraper._extract_name(None) == ''

    def test_strips_whitespace_from_aria_label(self):
        soup = self._make_soup(
            '<a href="/maps/place/Spa" aria-label="  Day Spa  ">Spa</a>'
        )
        assert scraper._extract_name(soup) == 'Day Spa'

    def test_prefers_aria_label_over_heading(self):
        soup = self._make_soup(
            '<a href="/maps/place/Shop" aria-label="The Shop">'
            '<div role="heading">Different Heading</div></a>'
        )
        assert scraper._extract_name(soup) == 'The Shop'


class TestExtractRating:
    """Tests for _extract_rating helper."""

    def _make_soup(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'lxml')

    def test_extracts_rating_from_aria_label_stars(self):
        soup = self._make_soup('<span aria-label="4.5 stars">★★★★☆</span>')
        assert scraper._extract_rating(soup) == '4.5'

    def test_extracts_integer_rating(self):
        soup = self._make_soup('<span aria-label="5 stars">★★★★★</span>')
        assert scraper._extract_rating(soup) == '5'

    def test_falls_back_to_out_of_5_label(self):
        soup = self._make_soup('<span aria-label="Rated 3.8 out of 5">3.8</span>')
        assert scraper._extract_rating(soup) == '3.8'

    def test_returns_empty_string_when_no_rating(self):
        soup = self._make_soup('<div>no rating here</div>')
        assert scraper._extract_rating(soup) == ''

    def test_returns_empty_string_on_exception(self):
        assert scraper._extract_rating(None) == ''

    def test_handles_singular_star_label(self):
        soup = self._make_soup('<span aria-label="1 star">★</span>')
        assert scraper._extract_rating(soup) == '1'


class TestExtractReviewCount:
    """Tests for _extract_review_count helper."""

    def _make_soup(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'lxml')

    def test_extracts_simple_count(self):
        soup = self._make_soup('<span>(123)</span>')
        assert scraper._extract_review_count(soup) == '123'

    def test_extracts_count_with_comma_separator(self):
        soup = self._make_soup('<span>(1,234)</span>')
        assert scraper._extract_review_count(soup) == '1,234'

    def test_extracts_count_with_thousands(self):
        soup = self._make_soup('<span>(12,345)</span>')
        assert scraper._extract_review_count(soup) == '12,345'

    def test_returns_empty_string_when_no_count(self):
        soup = self._make_soup('<div>no reviews</div>')
        assert scraper._extract_review_count(soup) == ''

    def test_returns_empty_string_on_exception(self):
        assert scraper._extract_review_count(None) == ''

    def test_ignores_non_review_parenthesised_text(self):
        soup = self._make_soup('<span>(A)</span>')
        assert scraper._extract_review_count(soup) == ''

    def test_prefers_first_match_in_document_order(self):
        soup = self._make_soup('<span>(10)</span><span>(20)</span>')
        assert scraper._extract_review_count(soup) == '10'


class TestExtractPhone:
    """Tests for _extract_phone helper."""

    def _make_soup(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'lxml')

    def test_extracts_phone_from_data_item_id(self):
        soup = self._make_soup(
            '<span data-item-id="phone:tel:+442071234567">+44 207 123 4567</span>'
        )
        assert scraper._extract_phone(soup) == '+44 207 123 4567'

    def test_data_item_id_partial_match(self):
        soup = self._make_soup(
            '<div data-item-id="phone">020 7946 0958</div>'
        )
        assert scraper._extract_phone(soup) == '020 7946 0958'

    def test_falls_back_to_regex_when_no_data_item_id(self):
        soup = self._make_soup('<div>Call us: +1 (555) 234-5678</div>')
        result = scraper._extract_phone(soup)
        assert '+1' in result or '555' in result

    def test_nanp_format_matched_by_regex_fallback(self):
        soup = self._make_soup('<div>Phone: (800) 555-1212</div>')
        result = scraper._extract_phone(soup)
        assert '555' in result

    def test_returns_empty_string_when_no_phone(self):
        soup = self._make_soup('<div>no phone here</div>')
        assert scraper._extract_phone(soup) == ''

    def test_returns_empty_string_on_exception(self):
        assert scraper._extract_phone(None) == ''

    def test_strips_whitespace_from_data_item_id_text(self):
        soup = self._make_soup(
            '<span data-item-id="phone:tel:123">  +1 800 555 1234  </span>'
        )
        assert scraper._extract_phone(soup) == '+1 800 555 1234'


class TestExtractWebsite:
    """Tests for _extract_website helper."""

    def _make_soup(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'lxml')

    def test_extracts_website_from_authority_data_item_id(self):
        soup = self._make_soup(
            '<a data-item-id="authority" href="https://example.com">Website</a>'
        )
        assert scraper._extract_website(soup) == 'https://example.com'

    def test_falls_back_to_external_http_link(self):
        soup = self._make_soup(
            '<a href="https://www.mybusiness.co.uk">Visit us</a>'
        )
        assert scraper._extract_website(soup) == 'https://www.mybusiness.co.uk'

    def test_fallback_skips_google_links(self):
        soup = self._make_soup(
            '<a href="https://www.google.com/maps/place/X">See on Maps</a>'
            '<a href="https://www.mybusiness.co.uk">Our site</a>'
        )
        assert scraper._extract_website(soup) == 'https://www.mybusiness.co.uk'

    def test_fallback_skips_relative_links(self):
        soup = self._make_soup(
            '<a href="/local/path">local</a>'
            '<a href="https://external.com">external</a>'
        )
        assert scraper._extract_website(soup) == 'https://external.com'

    def test_returns_empty_string_when_no_website(self):
        soup = self._make_soup('<div>no links</div>')
        assert scraper._extract_website(soup) == ''

    def test_returns_empty_string_on_exception(self):
        assert scraper._extract_website(None) == ''

    def test_prefers_authority_over_fallback_external_link(self):
        soup = self._make_soup(
            '<a href="https://other.com">Other</a>'
            '<a data-item-id="authority" href="https://official.com">Official</a>'
        )
        assert scraper._extract_website(soup) == 'https://official.com'


class TestParseBusinessNode:
    """Tests for _parse_business_node orchestrator."""

    def _full_node_html(self):
        return (
            '<div>'
            '<a href="/maps/place/Coffee+Lab/ChIabc123" aria-label="Coffee Lab">'
            '<span aria-label="4.3 stars">4.3</span>'
            '<span>(892)</span>'
            '</a>'
            '<span data-item-id="phone:tel:+442071234567">+44 207 123 4567</span>'
            '<a data-item-id="authority" href="https://coffeelab.co.uk">Website</a>'
            '</div>'
        )

    def test_returns_dict_with_all_fields(self):
        result = scraper._parse_business_node(self._full_node_html())
        assert isinstance(result, dict)
        for key in ('name', 'rating', 'reviews', 'phone', 'website'):
            assert key in result

    def test_full_extraction_from_rich_node(self):
        result = scraper._parse_business_node(self._full_node_html())
        assert result['name'] == 'Coffee Lab'
        assert result['rating'] == '4.3'
        assert result['reviews'] == '892'
        assert result['phone'] == '+44 207 123 4567'
        assert result['website'] == 'https://coffeelab.co.uk'

    def test_returns_dict_with_empty_strings_on_minimal_node(self):
        result = scraper._parse_business_node('<div><p>nothing</p></div>')
        assert result == {'name': '', 'rating': '', 'reviews': '', 'phone': '', 'website': ''}

    def test_does_not_raise_on_empty_string(self):
        result = scraper._parse_business_node('')
        assert isinstance(result, dict)

    def test_does_not_raise_on_malformed_html(self):
        result = scraper._parse_business_node('<<<<</>>>')
        assert isinstance(result, dict)

    def test_uses_lxml_parser(self, monkeypatch):
        """Verify BeautifulSoup is called with 'lxml' parser."""
        calls = []
        original_bs = scraper.BeautifulSoup

        def spy_bs(markup, parser):
            calls.append(parser)
            return original_bs(markup, parser)

        monkeypatch.setattr(scraper, 'BeautifulSoup', spy_bs)
        scraper._parse_business_node('<div></div>')
        assert calls == ['lxml']

    def test_returns_empty_dict_on_catastrophic_failure(self, monkeypatch):
        """Exception in BeautifulSoup construction returns empty dict."""
        def failing_bs(markup, parser):
            raise RuntimeError('catastrophic failure')

        monkeypatch.setattr(scraper, 'BeautifulSoup', failing_bs)
        result = scraper._parse_business_node('<div></div>')
        assert result == {'name': '', 'rating': '', 'reviews': '', 'phone': '', 'website': ''}


class TestCollectNodes:
    """Tests for _collect_nodes Playwright-side HTML gatherer."""

    def test_returns_list_of_html_strings(self):
        mock_page = MagicMock()
        mock_feed_el = MagicMock()
        mock_page.query_selector.return_value = mock_feed_el

        anchor1 = MagicMock()
        anchor2 = MagicMock()
        mock_feed_el.query_selector_all.return_value = [anchor1, anchor2]

        anchor1.get_attribute.return_value = '/maps/place/CafeA?q=a'
        anchor2.get_attribute.return_value = '/maps/place/CafeB?q=b'

        anchor1.evaluate.return_value = '<div>CafeA HTML</div>'
        anchor2.evaluate.return_value = '<div>CafeB HTML</div>'

        result = scraper._collect_nodes(mock_page)
        assert result == ['<div>CafeA HTML</div>', '<div>CafeB HTML</div>']

    def test_deduplicates_anchors_sharing_same_place_path(self):
        mock_page = MagicMock()
        mock_feed_el = MagicMock()
        mock_page.query_selector.return_value = mock_feed_el

        anchor1 = MagicMock()
        anchor2 = MagicMock()
        mock_feed_el.query_selector_all.return_value = [anchor1, anchor2]

        anchor1.get_attribute.return_value = '/maps/place/CafeA?data=1'
        anchor2.get_attribute.return_value = '/maps/place/CafeA?data=2'

        anchor1.evaluate.return_value = '<div>CafeA HTML</div>'

        result = scraper._collect_nodes(mock_page)
        assert len(result) == 1

    def test_returns_empty_list_when_feed_not_found(self):
        mock_page = MagicMock()
        mock_page.query_selector.return_value = None

        result = scraper._collect_nodes(mock_page)
        assert result == []

    def test_skips_anchor_on_evaluate_exception(self):
        mock_page = MagicMock()
        mock_feed_el = MagicMock()
        mock_page.query_selector.return_value = mock_feed_el

        anchor1 = MagicMock()
        anchor2 = MagicMock()
        mock_feed_el.query_selector_all.return_value = [anchor1, anchor2]

        anchor1.get_attribute.return_value = '/maps/place/CafeA'
        anchor2.get_attribute.return_value = '/maps/place/CafeB'

        anchor1.evaluate.side_effect = Exception('DOM error')
        anchor2.evaluate.return_value = '<div>CafeB HTML</div>'

        result = scraper._collect_nodes(mock_page)
        assert result == ['<div>CafeB HTML</div>']

    def test_queries_feed_with_role_selector_first(self):
        mock_page = MagicMock()
        mock_page.query_selector.return_value = None

        scraper._collect_nodes(mock_page)

        first_call = mock_page.query_selector.call_args_list[0]
        assert 'role="feed"' in first_call[0][0]

    def test_passes_place_link_selector_to_query_selector_all(self):
        mock_page = MagicMock()
        mock_feed_el = MagicMock()
        mock_page.query_selector.return_value = mock_feed_el
        mock_feed_el.query_selector_all.return_value = []

        scraper._collect_nodes(mock_page)

        call_selector = mock_feed_el.query_selector_all.call_args[0][0]
        assert scraper._PLACE_LINK_SELECTOR == call_selector

    def test_collect_nodes_uses_aria_label_fallback_when_role_feed_absent(self):
        mock_page = MagicMock()
        mock_feed_el = MagicMock()
        mock_feed_el.query_selector_all.return_value = []

        mock_page.query_selector.side_effect = [None, mock_feed_el]

        result = scraper._collect_nodes(mock_page)

        assert mock_page.query_selector.call_count == 2
        second_call = mock_page.query_selector.call_args_list[1][0][0]
        assert 'aria-label' in second_call
        assert result == []


class TestScrapeReturnsResults:
    """Tests that scrape() returns parsed results from _collect_nodes."""

    @patch('scraper.sync_playwright')
    def test_scrape_returns_non_empty_list_when_nodes_found(self, mock_pw):
        mock_p, mock_browser, mock_ctx, mock_page = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        mock_pw.return_value.__enter__.return_value = mock_p
        mock_pw.return_value.__exit__.return_value = None
        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_ctx.__enter__.return_value = mock_ctx
        mock_ctx.__exit__.return_value = None
        mock_ctx.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_ctx

        fake_result = {'name': 'Cafe', 'rating': '4.5', 'reviews': '100', 'phone': '', 'website': ''}

        with patch('scraper._dismiss_consent'), \
             patch('scraper._scroll_feed'), \
             patch('scraper._collect_nodes', return_value=['<div></div>']), \
             patch('scraper._parse_business_node', return_value=fake_result):
            result = scraper.scrape('https://www.google.com/maps/search/cafes')

        assert result == [fake_result]

    @patch('scraper.sync_playwright')
    def test_scrape_filters_out_nodes_with_empty_name(self, mock_pw):
        mock_p, mock_browser, mock_ctx, mock_page = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        mock_pw.return_value.__enter__.return_value = mock_p
        mock_pw.return_value.__exit__.return_value = None
        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_ctx.__enter__.return_value = mock_ctx
        mock_ctx.__exit__.return_value = None
        mock_ctx.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_ctx

        nameless = {'name': '', 'rating': '', 'reviews': '', 'phone': '', 'website': ''}

        with patch('scraper._dismiss_consent'), \
             patch('scraper._scroll_feed'), \
             patch('scraper._collect_nodes', return_value=['<div></div>']), \
             patch('scraper._parse_business_node', return_value=nameless):
            result = scraper.scrape('https://www.google.com/maps/search/cafes')

        assert result == []

    @patch('scraper.sync_playwright')
    def test_scrape_calls_collect_nodes_after_scroll(self, mock_pw):
        mock_p, mock_browser, mock_ctx, mock_page = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        mock_pw.return_value.__enter__.return_value = mock_p
        mock_pw.return_value.__exit__.return_value = None
        mock_p.chromium.launch.return_value.__enter__.return_value = mock_browser
        mock_p.chromium.launch.return_value.__exit__.return_value = None
        mock_ctx.__enter__.return_value = mock_ctx
        mock_ctx.__exit__.return_value = None
        mock_ctx.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_ctx

        call_order = []

        with patch('scraper._dismiss_consent'), \
             patch('scraper._scroll_feed', side_effect=lambda *a: call_order.append('scroll')), \
             patch('scraper._collect_nodes',
                   side_effect=lambda *a: call_order.append('collect') or []), \
             patch('scraper._parse_business_node', return_value={'name': '', 'rating': '', 'reviews': '', 'phone': '', 'website': ''}):
            scraper.scrape('https://www.google.com/maps/search/test')

        assert call_order.index('scroll') < call_order.index('collect')
