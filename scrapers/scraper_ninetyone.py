"""
scraper_ninetyone.py — Ninety One, Brick Lane (91bricklane.pub)
Jazz on the Lane series — Sundays, DICE-ticketed.
Site is JS-rendered — requires Playwright.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from browser import fetch_browser, PLAYWRIGHT_AVAILABLE

VENUE       = "Ninety One"
ZONE        = "East"
HOOD        = "Brick Lane"
TUBE        = "Shoreditch High Street"
TIER        = "2"
BASE_URL    = "https://91bricklane.pub"
EVENTS_URL  = f"{BASE_URL}/"
SOURCE_URL  = EVENTS_URL


def scrape() -> list:
    print("Scraping Ninety One (Playwright)...")
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available — skipping")
        return []

    soup = fetch_browser(EVENTS_URL,
        wait_for="[class*='event'], article, .event-item, a[href*='dice'], a[href*='ticket']",
        timeout=35000)
    if not soup:
        print("  No response from Ninety One")
        return []

    results = []
    # Look for DICE links which contain the event date in the URL
    dice_links = soup.find_all("a", href=re.compile(r"dice\.fm/event/"))
    print(f"  Found {len(dice_links)} DICE event links")

    seen = set()
    for link in dice_links:
        href = link.get("href", "")
        text = link.get_text(separator=" ", strip=True)

        # Extract date from URL slug e.g. "jazz-on-the-lane-14th-jun"
        date_m = re.search(
            r"(\d{1,2})(?:st|nd|rd|th)-"
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            href, re.I
        )
        if not date_m:
            # Try text
            date_m = re.search(
                r"(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
                text, re.I
            )
        if not date_m:
            continue

        import datetime
        day = int(date_m.group(1))
        mon = date_m.group(2)[:3].capitalize()
        year = datetime.date.today().year
        date_str = clean_date(f"{day} {mon} {year}")
        if not date_str or not is_future(date_str):
            continue

        artist = text.split("|")[0].strip() or text.split("–")[0].strip() or "Jazz on the Lane"
        artist = re.sub(r"\d{1,2}(st|nd|rd|th)?\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).*", "", artist, flags=re.I).strip()
        if not artist or len(artist) < 3:
            artist = "Jazz on the Lane"

        key = f"{artist.lower()}-{date_str}"
        if key in seen:
            continue
        seen.add(key)

        results.append(gig(
            artist_name=artist, venue_name=VENUE, date=date_str,
            ticket_url=href, source_url=SOURCE_URL,
            zone=ZONE, neighbourhood=HOOD, nearest_tube=TUBE,
            venue_tier=TIER, format_tags="Standing / Gig",
            genre_tier1="Contemporary Jazz",
            special_occasion="Jazz on the Lane",
        ))

    print(f"  Found {len(results)} future Ninety One gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No Ninety One gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Ninety One gigs")


if __name__ == "__main__":
    run()
