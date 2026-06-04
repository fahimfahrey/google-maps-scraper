"""Automation logic: Playwright-driven scraping with stealth."""

import random
import time
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
_FEED_SELECTORS = ('div[role="feed"]', '[aria-label*="Results"]')
_END_OF_LIST_TEXT = "You've reached the end of the list"


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


def scrape(url: str) -> list[dict]:
    """Scrape `url` and return list of result dicts."""
    with sync_playwright() as p:
        with p.chromium.launch(headless=True, args=_LAUNCH_ARGS) as browser:
            with _build_context(browser) as context:
                page = context.new_page()
                _block_media(page)
                page.goto(_MAPS_URL, wait_until="networkidle")
                _dismiss_consent(page)
    return []


if __name__ == "__main__":
    result = scrape("unused")
    print("Browser init OK, consent dismissed, result:", result)
