"""
scraper_kingsplace.py — King's Place, Kings Cross
Source: https://www.kingsplace.co.uk/whats-on/jazz/
403 blocked for regular requests — uses Playwright.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from browser import fetch_browser, PLAYWRIGHT_AVAILABLE

VENUE    = "King's Place"
ZONE     = "Central"
HOOD     = "Barbican / City"
BASE_URL = "https://www.kingsplace.co.uk"
EVENTS   = f"{BASE_URL}/whats-on/jazz/"


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available")
        return []

    soup = fetch_browser(EVENTS, wait_for=".event-card, .production, article")
    if not soup:
        return []

    results = []
    event_blocks = (
        soup.select("div.event-card") or
        soup.select("article") or
        soup.select("div[class*='production']") or
        soup.select("li[class*='event']") or
        []
    )

    for block in event_blocks:
        text = block.get_text(separator=" ", strip=True)
        h = block.find(["h1","h2","h3","h4"])
        artist = h.get_text(strip=True) if h else ""
        if not artist or len(artist) < 3:
            continue

        date_m = re.search(
            r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
            r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
            r"Nov(?:ember)?|Dec(?:ember)?)(?:\s+(\d{4}))?",
            text, re.IGNORECASE
        )
        if not date_m:
            continue
        year = date_m.group(3) or "2026"
        date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")
        if not is_future(date_str):
            continue

        time_m  = re.search(r"(\d{1,2}[:.]\d{2})\s*(pm|am)?", text, re.I)
        price_m = re.search(r"£(\d+)", text)
        link    = block.find("a", href=True)
        href    = link["href"] if link else ""
        ticket_url = href if href.startswith("http") else (BASE_URL + href if href else EVENTS)

        results.append(gig(
            artist_name=artist,
            venue_name=VENUE,
            date=date_str,
            start_time=time_m.group(0) if time_m else "",
            price_from=f"£{price_m.group(1)}" if price_m else "",
            ticket_url=ticket_url,
            source_url=EVENTS,
            zone=ZONE,
            neighbourhood=HOOD,
            format_tags="Concert Hall",
            genre_tier1="Contemporary Jazz",
            venue_tier="2",
        ))

    print(f"  Found {len(results)} future King's Place gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new King's Place gigs")


if __name__ == "__main__":
    run()
