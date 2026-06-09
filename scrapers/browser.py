"""
browser.py — Playwright browser helper
Provides a fetch_with_browser() function that uses a real Chrome browser
to bypass Cloudflare and JavaScript rendering.
Falls back gracefully if Playwright is not installed.
"""
import os
import sys
from pathlib import Path

# Try importing playwright — graceful fallback if not installed
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("  WARNING: playwright not installed — browser fetching unavailable")

from bs4 import BeautifulSoup


def fetch_browser(url: str, wait_for: str = None, timeout: int = 30000) -> BeautifulSoup | None:
    """
    Fetch a URL using a real headless Chrome browser.
    Bypasses Cloudflare bot protection and renders JavaScript.
    
    Args:
        url: The URL to fetch
        wait_for: CSS selector to wait for before returning (optional)
        timeout: Timeout in milliseconds (default 30s)
    
    Returns:
        BeautifulSoup object or None if failed
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                ]
            )

            context = browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0.0.0 Safari/537.36'
                ),
                viewport={'width': 1280, 'height': 800},
                locale='en-GB',
            )

            page = context.new_page()

            # Block images, fonts and stylesheets to speed things up
            page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,css}", 
                      lambda route: route.abort())

            page.goto(url, wait_until='domcontentloaded', timeout=timeout)

            # Wait for specific element if requested
            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=5000)
                except Exception:
                    pass  # Continue even if selector not found

            # Small delay for JS to settle
            page.wait_for_timeout(1500)

            html = page.content()
            browser.close()

            return BeautifulSoup(html, 'lxml')

    except Exception as e:
        print(f"  Browser fetch error for {url}: {e}")
        return None


def fetch_browser_text(url: str, wait_for: str = None) -> str | None:
    """Returns plain text content of a page."""
    soup = fetch_browser(url, wait_for=wait_for)
    if not soup:
        return None
    return soup.get_text(separator='\n', strip=True)
