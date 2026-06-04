"""Automation logic: Playwright-driven scraping with stealth."""

import re
import random
import time
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
from bs4 import BeautifulSoup


# Module-level constants
_MAPS_URL = "https://www.google.com/maps"
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
]
_CONSENT_TEXTS = ["Accept all", "Alle akzeptieren", "Tout accepter", "Aceitar tudo"]
_CONSENT_TIMEOUT_MS = 5_000
_SCROLL_STEP_PX = 2_000
_SCROLL_JITTER_MIN = 1.5
_SCROLL_JITTER_MAX = 3.5
_SCROLL_STALE_LIMIT = 3
_PROFILE_DELAY_MIN = 2.0
_PROFILE_DELAY_MAX = 5.0
_INTER_QUERY_DELAY_MIN = 5.0
_INTER_QUERY_DELAY_MAX = 15.0
_SPEED_PRESETS: dict[str, tuple[float, float]] = {
    "slow":   (15.0, 30.0),
    "normal": (_INTER_QUERY_DELAY_MIN, _INTER_QUERY_DELAY_MAX),
    "fast":   (1.5,  5.0),
}
_FEED_SELECTORS = ('div[role="feed"]', '[aria-label*="Results"]')
_END_OF_LIST_TEXT = "You've reached the end of the list"
_PLACE_LINK_SELECTOR = 'a[href*="/maps/place/"]'
_WEBSITE_ITEM_ID = 'authority'
_PHONE_ITEM_ID = 'phone'
_PHONE_REGEX = re.compile(
    r'(?:'
    r'\+\d{1,3}[\s\-\.]?\(?\d{1,4}\)?[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,9}'
    r'|\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}'
    r'|\d{4,5}[\s\-]\d{5,6}'
    r')'
)


def _query_to_url(query: str) -> str:
    return f"{_MAPS_URL}/search/{quote_plus(query)}"


def _extract_name(soup) -> str:
    try:
        link = soup.select_one(_PLACE_LINK_SELECTOR)
        if link:
            label = link.get('aria-label', '').strip()
            if label:
                return label
        heading = soup.select_one('[role="heading"]')
        if heading:
            return heading.get_text(strip=True)
    except Exception:
        pass
    return ''


def _extract_rating(soup) -> str:
    try:
        star_el = soup.select_one('[aria-label*=" stars"]') or \
                  soup.select_one('[aria-label*=" star"]')
        if star_el:
            m = re.search(r'(\d+\.?\d*)\s+stars?', star_el.get('aria-label', ''))
            if m:
                return m.group(1)
        out_of_el = soup.select_one('[aria-label*="out of 5"]')
        if out_of_el:
            m = re.search(r'(\d+\.?\d*)\s+out of 5', out_of_el.get('aria-label', ''))
            if m:
                return m.group(1)
    except Exception:
        pass
    return ''


def _extract_review_count(soup) -> str:
    try:
        for text_node in soup.find_all(string=re.compile(r'\(\d[\d,]*\)')):
            m = re.search(r'\((\d[\d,]*)\)', text_node)
            if m:
                return m.group(1)
    except Exception:
        pass
    return ''


def _extract_phone(soup) -> str:
    try:
        phone_el = soup.select_one(f'[data-item-id*="{_PHONE_ITEM_ID}"]')
        if phone_el:
            return phone_el.get_text(strip=True)
        m = _PHONE_REGEX.search(soup.get_text(' '))
        if m:
            return m.group(0).strip()
    except Exception:
        pass
    return ''


def _extract_website(soup) -> str:
    try:
        web_el = soup.select_one(f'a[data-item-id="{_WEBSITE_ITEM_ID}"]')
        if web_el:
            return web_el.get('href', '')
        for link in soup.select('a[href^="http"]'):
            href = link.get('href', '')
            if 'google.com' not in href:
                return href
    except Exception:
        pass
    return ''


def _parse_business_node(html: str) -> dict:
    """Parse inner HTML of one business card node into a field dict.

    Returns a dict with keys: name, rating, reviews, phone, website.
    Every field defaults to '' on extraction failure.
    """
    try:
        soup = BeautifulSoup(html, 'lxml')
        return {
            'name': _extract_name(soup),
            'rating': _extract_rating(soup),
            'reviews': _extract_review_count(soup),
            'phone': _extract_phone(soup),
            'website': _extract_website(soup),
        }
    except Exception:
        return {'name': '', 'rating': '', 'reviews': '', 'phone': '', 'website': ''}


def _collect_nodes(page) -> list[str]:
    """Collect inner HTML strings for each unique business node in the feed.

    Queries within the feed container to avoid promoted pins outside the panel.
    De-duplicates by /maps/place/ path (strips query string) so photo anchors
    and title anchors pointing to the same place are only collected once.
    """
    feed_el = (
        page.query_selector('div[role="feed"]')
        or page.query_selector('[aria-label*="Results"]')
    )
    if not feed_el:
        return []

    anchors = feed_el.query_selector_all(_PLACE_LINK_SELECTOR)
    seen: set[str] = set()
    results: list[str] = []

    for anchor in anchors:
        try:
            href = anchor.get_attribute('href') or ''
            key = href.split('?')[0]
            if key in seen:
                continue
            seen.add(key)
            html = anchor.evaluate(
                '(el) => (el.closest("[jsaction]") || el.parentElement).innerHTML'
            )
            results.append(html)
            time.sleep(random.uniform(_PROFILE_DELAY_MIN, _PROFILE_DELAY_MAX))
        except Exception:
            continue

    return results


def _build_context(browser):
    """Create and stealth-configure a BrowserContext."""
    context = browser.new_context(
        user_agent=_USER_AGENT,
        viewport={"width": 1280, "height": 800},
    )
    Stealth().apply_stealth_sync(context)
    return context


def _dismiss_consent(page) -> None:
    """Detect and click 'Accept all' consent button if present."""
    selector = ", ".join(
        f'button:has-text("{text}")' for text in _CONSENT_TEXTS
    )
    try:
        page.locator(selector).first.click(timeout=_CONSENT_TIMEOUT_MS)
        page.wait_for_load_state("networkidle")
    except PlaywrightTimeoutError:
        pass


def _block_media(page) -> None:
    """Abort image and font requests to reduce bandwidth."""
    page.route(
        "**/*.{png,jpg,jpeg,svg,gif,webp,woff,woff2,ttf,eot,ico}",
        lambda route: route.abort(),
    )


def _locate_feed(page):
    """Return .first locator for the Maps results feed container.

    Raises RuntimeError if no selector in _FEED_SELECTORS matches.
    """
    for selector in _FEED_SELECTORS:
        loc = page.locator(selector)
        if loc.count() > 0:
            return loc.first
    raise RuntimeError(
        f"Maps feed container not found. Tried: {list(_FEED_SELECTORS)}"
    )


def _end_of_list_visible(page) -> bool:
    """Return True if the Maps end-of-results notice is present in the DOM."""
    return page.locator(f'text="{_END_OF_LIST_TEXT}"').count() > 0


def _scroll_feed(page) -> None:
    """Scroll the Maps results feed until all results load.

    Stops when 'end of list' notice appears or _SCROLL_STALE_LIMIT consecutive
    scrolls produce no scrollHeight increase.
    """
    feed = _locate_feed(page)
    handle = feed.element_handle()
    prev_height = 0
    stale_count = 0

    while True:
        if _end_of_list_visible(page):
            break

        current_height = page.evaluate(
            "(args) => { args[0].scrollBy(0, args[1]); return args[0].scrollHeight; }",
            [handle, _SCROLL_STEP_PX],
        )
        time.sleep(random.uniform(_SCROLL_JITTER_MIN, _SCROLL_JITTER_MAX))

        if current_height <= prev_height:
            stale_count += 1
            if stale_count >= _SCROLL_STALE_LIMIT:
                break
        else:
            stale_count = 0
            prev_height = current_height


def _scrape_one_url(browser, url: str) -> list[dict]:
    """Run one full scrape cycle against `url` on an existing browser.

    Creates a fresh BrowserContext (clears cookies/storage), navigates,
    scrolls, collects nodes, and parses results.  The context is closed
    when the with-block exits regardless of errors.
    """
    with _build_context(browser) as ctx:
        page = ctx.new_page()
        _block_media(page)
        page.goto(url, wait_until="networkidle")
        _dismiss_consent(page)
        _scroll_feed(page)
        nodes_html = _collect_nodes(page)
    return [r for r in (_parse_business_node(h) for h in nodes_html) if r.get('name')]


def scrape(url: str) -> list[dict]:
    """Scrape `url` and return list of result dicts."""
    with sync_playwright() as p:
        with p.chromium.launch(headless=True, args=_LAUNCH_ARGS) as browser:
            return _scrape_one_url(browser, url)


def scrape_multi(queries: list[str], delay_preset: str = "normal") -> list[dict]:
    """Scrape multiple sub-region queries and return deduplicated results.

    Each query runs in its own fresh BrowserContext so cookies and
    local-storage tracking state are cleared between iterations.
    A randomised inter-query delay mimics human pacing between searches.
    Results from all queries are merged and deduplicated by name+phone key.
    """
    seen_keys: set[str] = set()
    results: list[dict] = []
    with sync_playwright() as p:
        with p.chromium.launch(headless=True, args=_LAUNCH_ARGS) as browser:
            for i, query in enumerate(queries):
                url = _query_to_url(query)
                batch = _scrape_one_url(browser, url)
                for record in batch:
                    key = f"{record.get('name', '')}|{record.get('phone', '')}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        results.append(record)
                if i < len(queries) - 1:
                    delay_min, delay_max = _SPEED_PRESETS.get(
                        delay_preset, _SPEED_PRESETS["normal"]
                    )
                    time.sleep(random.uniform(delay_min, delay_max))
    return results


if __name__ == "__main__":  # pragma: no cover
    result = scrape("https://www.google.com/maps/search/coffee+shops+london")
    print("Scroll complete, results:", result)
