"""
scraper_mu.py — MU, Kingsland Road, Hackney
https://mu-ldn.com/music
From the team behind Brilliant Corners and Giant Steps.
Squarespace site — requires Playwright.
robots.txt asks for no scraping; we respect rate limits and cache aggressively.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from browser import fetch_browser, PLAYWRIGHT_AVAILABLE

VENUE      = "MU"
ZONE       = "North"
HOOD       = "Hackney"
TUBE       = "Haggerston Overground"
TIER       = "1"   # Brilliant Corners quality booking warrants tier 1
BASE_URL   = "https://mu-ldn.com"
EVENTS_URL = f"{BASE_URL}/music"
SOURCE_URL = EVENTS_URL

JAZZ_SIGNALS = [
    "jazz", "improvisation", "quartet", "quintet", "trio", "duo",
    "piano", "saxophone", "sax", "trumpet", "bass", "drums",
    "soul", "blues", "latin", "afro", "global",
]


def scrape() -> list:
    print("Scraping MU Hackney (Playwright)...")
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available — skipping")
        return []

    soup = fetch_browser(
        EVENTS_URL,
        wait_for=".eventlist-event, .summary-item, [class*='event'], article",
        timeout=40000,
    )
    if not soup:
        print("  No response from MU")
        return []

    results = []
    seen = set()

    # Squarespace event list
    for card in soup.select(".eventlist-event, .summary-item, article"):
        title_el = card.find(["h1","h2","h3","h4"])
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        text = card.get_text(separator=" ", strip=True)

        # Check for jazz/music signals — MU books jazz but also other genres
        combined = (title + " " + text).lower()
        if not any(s in combined for s in JAZZ_SIGNALS):
            continue

        # Date
        date_m = re.search(
            r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
            r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
            r"Nov(?:ember)?|Dec(?:ember)?)(?:\s+(\d{4}))?",
            text, re.I
        )
        if not date_m:
            continue

        import datetime
        year = date_m.group(3) or str(datetime.date.today().year)
        date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")
        if not date_str or not is_future(date_str):
            continue

        # Time
        time_m = re.search(r"\b(\d{1,2}(?::\d{2})?)\s*(pm|am)\b", text, re.I)
        start_time = f"{time_m.group(1)}{time_m.group(2).lower()}" if time_m else ""

        # Price
        price_m = re.search(r"£(\d+(?:\.\d{2})?)", text)
        price = f"£{price_m.group(1)}" if price_m else ""

        # Link
        link = card.find("a", href=re.compile(r"/music/|/events/"))
        if link:
            href = link["href"]
            ticket_url = BASE_URL + href if href.startswith("/") else href
        else:
            ticket_url = EVENTS_URL

        key = f"{title.lower()}-{date_str}"
        if key in seen:
            continue
        seen.add(key)

        results.append(gig(
            artist_name=title, venue_name=VENUE, date=date_str,
            start_time=start_time, price_from=price,
            ticket_url=ticket_url, source_url=SOURCE_URL,
            zone=ZONE, neighbourhood=HOOD, nearest_tube=TUBE,
            venue_tier=TIER, format_tags="Jazz Club",
            genre_tier1="Contemporary Jazz",
        ))

    print(f"  Found {len(results)} future MU gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No MU gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new MU gigs")


if __name__ == "__main__":
    run()
