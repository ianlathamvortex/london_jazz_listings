"""
scraper_troubadour.py — Troubadour London Sunday Jazz
https://www.troubadourlondon.com/sunday-jazz
Wix site — JS-rendered, requires Playwright.
Sunday residency directed by Sebastiaan de Krom.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from browser import fetch_browser, PLAYWRIGHT_AVAILABLE

VENUE      = "Troubadour"
ZONE       = "West"
HOOD       = "Earl's Court"
TUBE       = "Earl's Court"
TIER       = "2"
BASE_URL   = "https://www.troubadourlondon.com"
EVENTS_URL = f"{BASE_URL}/sunday-jazz"
SOURCE_URL = EVENTS_URL


def scrape() -> list:
    print("Scraping Troubadour Sunday Jazz (Playwright)...")
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available — skipping")
        return []

    soup = fetch_browser(EVENTS_URL,
        wait_for="[class*='event'], [data-testid*='event'], [class*='date'], h2, h3",
        timeout=35000)
    if not soup:
        print("  No response from Troubadour")
        return []

    results = []
    seen = set()

    # Wix sites put event info in various block types
    # Look for date patterns in text, then find associated artist names
    text_blocks = soup.find_all(["h1","h2","h3","h4","p","div","span"])

    current_date = None
    for block in text_blocks:
        text = block.get_text(strip=True)
        if not text or len(text) > 200:
            continue

        # Date pattern
        date_m = re.search(
            r"(\d{1,2})\s*(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
            r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
            r"Nov(?:ember)?|Dec(?:ember)?)\s*(\d{4})?",
            text, re.I
        )
        if date_m:
            import datetime
            year = date_m.group(3) or str(datetime.date.today().year)
            date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")
            if date_str and is_future(date_str):
                current_date = date_str
            continue

        # Artist name — look for non-generic text near a known date
        if current_date and len(text) > 5 and len(text) < 80:
            skip_words = ["sunday", "jazz", "book", "ticket", "menu", "contact",
                          "troubadour", "reserv", "dinner", "information", "sebastiaan"]
            if not any(s in text.lower() for s in skip_words):
                key = f"{text.lower()}-{current_date}"
                if key not in seen:
                    seen.add(key)
                    # Get ticket link
                    parent_link = block.find_parent("a")
                    ticket_url = (BASE_URL + parent_link["href"]
                                  if parent_link and parent_link.get("href","").startswith("/")
                                  else parent_link["href"] if parent_link
                                  else EVENTS_URL)

                    results.append(gig(
                        artist_name=text, venue_name=VENUE, date=current_date,
                        ticket_url=ticket_url, source_url=SOURCE_URL,
                        zone=ZONE, neighbourhood=HOOD, nearest_tube=TUBE,
                        venue_tier=TIER, format_tags="Dining",
                        genre_tier1="Contemporary Jazz",
                    ))

    print(f"  Found {len(results)} future Troubadour Sunday Jazz gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No Troubadour gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Troubadour Sunday Jazz gigs")


if __name__ == "__main__":
    run()
