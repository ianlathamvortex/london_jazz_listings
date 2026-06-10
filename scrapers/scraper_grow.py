"""
scraper_grow.py — Grow Hackney
Sources:
  - https://www.growhackney.co.uk/jazz         (ticketed weekly jazz → gigs.json)
  - https://www.growhackney.co.uk/canalside-sessions (free Sunday series → free_entry.json)

Squarespace site — Cloudflare protected — requires Playwright.
Event data is in Squarespace's standard .eventlist-event blocks after JS renders.
"""

import re
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from browser import fetch_browser, PLAYWRIGHT_AVAILABLE

VENUE      = "Grow"
ZONE       = "East"
HOOD       = "Hackney Wick"
ADDRESS    = "98c Wallis Road, E9 5LN"
BASE_URL   = "https://www.growhackney.co.uk"
JAZZ_URL   = f"{BASE_URL}/jazz"
CANAL_URL  = f"{BASE_URL}/canalside-sessions"

# Squarespace event block selectors — standard across SS sites
SS_SELECTORS = [
    "article.eventlist-event",
    "div.eventlist-event",
    "li.eventlist-event",
    ".summary-item",
    "article[class*='event']",
    "div[class*='event-item']",
]

# Jazz filter — Canalside page has mixed content
JAZZ_HINTS = [
    "jazz", "afro", "latin", "samba", "blues", "soul", "swing",
    "bebop", "improv", "trumpet", "saxophone", "piano trio", "quartet",
    "williams cumberbache", "cumberbache",
]

def _is_jazz(text: str) -> bool:
    tl = text.lower()
    return any(h in tl for h in JAZZ_HINTS)


def _parse_squarespace_date(block) -> str | None:
    """
    Squarespace stores event dates in <time datetime="YYYY-MM-DDTHH:MM:SS">
    or in visible text like 'Sunday, June 21, 2026'.
    """
    # Try <time> element first — most reliable
    time_el = block.find("time", attrs={"datetime": True})
    if time_el:
        dt_raw = time_el["datetime"][:10]  # "2026-06-21"
        try:
            datetime.strptime(dt_raw, "%Y-%m-%d")
            return dt_raw
        except ValueError:
            pass

    # Fall back to text parsing
    text = block.get_text(separator=" ", strip=True)
    m = re.search(
        r"((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,?\s*)?"
        r"(\d{1,2})\s+"
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"(?:\s+(\d{4}))?",
        text, re.IGNORECASE
    )
    if m:
        year = m.group(4) or str(datetime.now().year)
        return clean_date(f"{m.group(2)} {m.group(3)} {year}")
    return None


def _parse_time(text: str) -> str:
    m = re.search(r"(\d{1,2})[.:h](\d{2})\s*(am|pm)?", text, re.I)
    if not m:
        m = re.search(r"(\d{1,2})\s*(am|pm)", text, re.I)
        if m:
            return f"{m.group(1)}{m.group(2).lower()}"
        return ""
    h, mn = m.group(1), m.group(2)
    suffix = m.group(3).lower() if m.group(3) else ""
    return f"{h}.{mn}{suffix}"


def _scrape_page(url: str, is_free: bool = False) -> list:
    """Scrape a single Grow event page. Returns list of gig dicts."""
    # Wait for any event block to appear — Squarespace uses .eventlist-event
    soup = fetch_browser(
        url,
        wait_for=".eventlist-event, .summary-item, article[class*='event'], div[class*='event-item']",
        timeout=40000,
    )
    if not soup:
        print(f"  No response from {url}")
        return []

    # Find event blocks — try each selector
    blocks = []
    for sel in SS_SELECTORS:
        blocks = soup.select(sel)
        if blocks:
            break

    if not blocks:
        # Fallback: any article or section with a date
        blocks = soup.find_all(["article", "section"]) or []

    print(f"  Found {len(blocks)} raw blocks at {url}")
    results = []

    for block in blocks:
        text = block.get_text(separator=" ", strip=True)

        # Title — usually in first h2/h3
        title_el = block.find(["h1", "h2", "h3", "h4"])
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or len(title) < 3:
            continue

        # Skip non-jazz on the Canalside page
        combined = title + " " + text
        if not _is_jazz(combined):
            continue

        date_str = _parse_squarespace_date(block)
        if not date_str or not is_future(date_str):
            continue

        time_str  = _parse_time(text)
        price_m   = re.search(r"£(\d+)", text)
        price     = f"£{price_m.group(1)}" if price_m and not is_free else ("Free" if is_free else "")

        # Ticket/event link
        link = block.find("a", href=re.compile(r"/events-calendar/"))
        if not link:
            link = block.find("a", href=True)
        href = link["href"] if link else ""
        ticket_url = (BASE_URL + href) if href.startswith("/") else (href or url)

        results.append(gig(
            artist_name=title,
            venue_name=VENUE,
            date=date_str,
            start_time=time_str,
            price_from=price,
            ticket_url=ticket_url,
            source_url=url,
            zone=ZONE,
            neighbourhood=HOOD,
            format_tags="Standing / Gig",
            genre_tier1="Contemporary Jazz",
            venue_tier="1",
        ))

    return results


def scrape_jazz() -> list:
    """Scrape ticketed jazz gigs → gigs.json"""
    print(f"Scraping {VENUE} (jazz page)...")
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available — skipping")
        return []
    results = _scrape_page(JAZZ_URL, is_free=False)
    print(f"  Found {len(results)} future jazz gigs")
    return results


def scrape_canalside() -> list:
    """Scrape Canalside Sessions (free entry) → free_entry.json"""
    print(f"Scraping {VENUE} (Canalside Sessions)...")
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available — skipping")
        return []
    results = _scrape_page(CANAL_URL, is_free=True)
    print(f"  Found {len(results)} future Canalside events")
    return results


def scrape() -> list:
    """Master scrape — called by run_all.py. Returns ticketed jazz gigs."""
    return scrape_jazz()


def run():
    # ── Ticketed jazz → gigs.json ─────────────────────────────
    jazz_gigs = scrape_jazz()
    if jazz_gigs:
        existing = load("gigs")
        merged, added = merge_gigs(existing, jazz_gigs)
        save("gigs", merged)
        print(f"  Added {added} new Grow jazz gigs")

    # ── Canalside Sessions → free_entry.json ──────────────────
    canal_events = scrape_canalside()
    if canal_events:
        # Convert to free_entry schema
        existing_free = load("free_entry")
        free_records = []
        for g in canal_events:
            free_records.append({
                "event_id":           g["gig_id"],
                "event_name":         g["artist_name"],
                "venue_name":         VENUE,
                "address":            ADDRESS,
                "zone":               ZONE,
                "neighbourhood":      HOOD,
                "date":               g["date"],
                "start_time":         g.get("start_time", "1pm"),
                "end_time":           "4pm",
                "price_from":         "Free",
                "description":        "Canalside Sessions — free Sunday afternoon jazz at Hackney Wick.",
                "booking_url":        g.get("ticket_url", CANAL_URL),
                "source_url":         CANAL_URL,
                "hidden":             False,
                "last_verified":      g.get("date_scraped", ""),
            })
        merged_free, added_free = merge_gigs(existing_free, free_records, id_field="event_id")
        save("free_entry", merged_free)
        print(f"  Added {added_free} new Canalside Sessions")


if __name__ == "__main__":
    run()
