"""
scraper_olivers.py — Oliver's Jazz Bar, Greenwich
https://oliversjazzbar.com/whats-on/

Their What's On page embeds a Google Calendar iframe.
Playwright loads the page, then navigates into the iframe to read events.
Falls back to fetching the Google Calendar embed URL directly.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from browser import PLAYWRIGHT_AVAILABLE

VENUE      = "Oliver's Jazz Bar"
ZONE       = "South East"
HOOD       = "Greenwich"
TUBE       = "Greenwich / Maze Hill"
TIER       = "1"
SOURCE_URL = "https://oliversjazzbar.com/whats-on/"
CAL_EMBED  = (
    "https://calendar.google.com/calendar/embed"
    "?height=600&wkst=1&ctz=Europe%2FLondon&bgcolor=%23ffffff"
    "&mode=AGENDA&showTitle=0&showNav=0&showDate=0&showPrint=0"
    "&showTabs=0&showCalendars=0&showTz=0"
    "&src=b2xpdmVyc2phenpiYXJAZ21haWwuY29t&color=%23a2845e"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,*/*",
}

MONTHS = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
}


def _parse_gcal_date(text: str) -> str | None:
    """Parse Google Calendar date formats like 'Mon 15 Jun' or 'Mon Jun 15'"""
    import datetime
    # 'Mon 15 Jun 2026' or 'Monday, June 15'
    m = re.search(
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:\s+(\d{4}))?",
        text, re.I
    )
    if m:
        day = int(m.group(1))
        mon = MONTHS.get(m.group(2).lower()[:3], 0)
        year = int(m.group(3)) if m.group(3) else datetime.date.today().year
        if mon:
            return f"{year}-{mon:02d}-{day:02d}"
    # 'Jun 15' or 'June 15 2026'
    m2 = re.search(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})(?:[,\s]+(\d{4}))?",
        text, re.I
    )
    if m2:
        mon = MONTHS.get(m2.group(1).lower()[:3], 0)
        day = int(m2.group(2))
        year = int(m2.group(3)) if m2.group(3) else datetime.date.today().year
        if mon:
            return f"{year}-{mon:02d}-{day:02d}"
    return None


def _scrape_gcal_embed() -> list:
    """Fetch the Google Calendar embed URL directly — sometimes works without JS"""
    import urllib.request
    try:
        req = urllib.request.Request(CAL_EMBED, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        return _parse_gcal_soup(soup)
    except Exception as e:
        print(f"  Direct calendar fetch failed: {e}")
        return []


def _parse_gcal_soup(soup) -> list:
    """Parse rendered Google Calendar HTML for events"""
    results = []
    seen = set()

    # Google Calendar agenda view renders events in table rows or divs
    # Each event has a date chip and a title
    for row in soup.find_all(["tr", "div", "li"]):
        text = row.get_text(separator=" ", strip=True)
        if not text or len(text) < 5:
            continue

        date_str = _parse_gcal_date(text)
        if not date_str or not is_future(date_str):
            continue

        # Event title — strip date/time noise
        title = re.sub(
            r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*[\s,]+", "", text, flags=re.I
        )
        title = re.sub(
            r"\d{1,2}[:/]\d{2}(\s*(am|pm))?", "", title, flags=re.I
        )
        title = re.sub(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}[,\s]*(\d{4})?",
            "", title, flags=re.I
        )
        title = title.strip(" ,·-–")

        if not title or len(title) < 4:
            continue

        # Skip generic/noise entries
        skip = ["more events", "no events", "loading", "calendar", "view all"]
        if any(s in title.lower() for s in skip):
            continue

        # Time
        time_m = re.search(r"\b(\d{1,2}(?::\d{2})?)\s*(pm|am)\b", text, re.I)
        start_time = f"{time_m.group(1)}{time_m.group(2).lower()}" if time_m else ""

        key = f"{title.lower().strip()}-{date_str}"
        if key in seen:
            continue
        seen.add(key)

        results.append(gig(
            artist_name=title, venue_name=VENUE, date=date_str,
            start_time=start_time, ticket_url=SOURCE_URL, source_url=SOURCE_URL,
            zone=ZONE, neighbourhood=HOOD, nearest_tube=TUBE,
            venue_tier=TIER, format_tags="Jazz Club",
            genre_tier1="Contemporary Jazz",
        ))

    return results


def scrape() -> list:
    print("Scraping Oliver's Jazz Bar (Google Calendar)...")
    results = []

    # Strategy 1: fetch Google Calendar embed directly
    results = _scrape_gcal_embed()
    if results:
        print(f"  Direct calendar fetch: {len(results)} events")
        return results

    # Strategy 2: Playwright — load the page and wait for iframe content
    if not PLAYWRIGHT_AVAILABLE:
        print("  No results and Playwright not available")
        return []

    try:
        from playwright.sync_api import sync_playwright
        from bs4 import BeautifulSoup

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Load the calendar embed directly in Playwright
            page.goto(CAL_EMBED, timeout=30000)
            page.wait_for_selector(".d2NRLb, .L1lMxb, tr[data-eventid]", timeout=20000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        results = _parse_gcal_soup(soup)
        print(f"  Playwright calendar: {len(results)} events")

    except Exception as e:
        print(f"  Playwright failed: {e}")

    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No Oliver's gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Oliver's Jazz Bar gigs")


if __name__ == "__main__":
    run()
