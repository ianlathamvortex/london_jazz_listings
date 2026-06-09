"""
scraper_cafeoto.py — Café OTO, Dalston
Source: https://www.cafeoto.co.uk/events/
JavaScript rendered — uses Playwright.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from browser import fetch_browser, PLAYWRIGHT_AVAILABLE

VENUE    = "Café OTO"
ZONE     = "North"
HOOD     = "Dalston"
BASE_URL = "https://www.cafeoto.co.uk"
EVENTS   = f"{BASE_URL}/events/"


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available")
        return []

    soup = fetch_browser(EVENTS, wait_for=".event, article, .events-list")
    if not soup:
        return []

    results = []

    # OTO uses standard event cards
    event_blocks = (
        soup.select("article") or
        soup.select("div.event") or
        soup.select("li.event") or
        soup.select("div[class*='event']") or
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
            format_tags="Standing / Gig",
            genre_tier1="Experimental / Free",
        ))

    print(f"  Found {len(results)} future Café OTO gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Café OTO gigs")


if __name__ == "__main__":
    run()
