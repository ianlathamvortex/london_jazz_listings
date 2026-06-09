"""
scraper_wigmorehall.py — Wigmore Hall jazz concerts
Source: https://www.wigmore-hall.org.uk/whats-on?genres=jazz
Wigmore Hall blocks standard requests — uses Playwright.
Jazz genre filter returns all jazz concerts.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, is_future
from browser import fetch_browser, PLAYWRIGHT_AVAILABLE

VENUE    = "Wigmore Hall"
ZONE     = "Central"
HOOD     = "Piccadilly"
BASE_URL = "https://www.wigmore-hall.org.uk"
JAZZ_URL = f"{BASE_URL}/whats-on?genres=jazz&page=1"


def scrape() -> list:
    print(f"Scraping {VENUE}...")

    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available — skipping Wigmore Hall")
        return []

    results = []

    for page in range(1, 5):
        url = f"{BASE_URL}/whats-on?genres=jazz&page={page}"
        print(f"  Fetching page {page}...")
        soup = fetch_browser(url, wait_for=".event-listing, .event-card, article")
        if not soup:
            break

        text = soup.get_text(separator="\n", strip=True)
        if len(text) < 500:
            break

        # Wigmore Hall event cards
        event_blocks = (
            soup.select("article") or
            soup.select("div.event-listing__item") or
            soup.select("div[class*='event']") or
            soup.select("li[class*='event']") or
            []
        )

        if not event_blocks:
            # Fallback: parse text directly
            page_results = _parse_text(text)
            results.extend(page_results)
            break

        for block in event_blocks:
            result = _parse_block(block)
            if result:
                results.append(result)

        # Check for next page
        if "next" not in text.lower() or page >= 4:
            break

    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r["gig_id"] not in seen:
            unique.append(r)
            seen.add(r["gig_id"])

    print(f"  Found {len(unique)} future Wigmore Hall jazz concerts")
    return unique


def _parse_block(block) -> dict | None:
    text = block.get_text(separator=" ", strip=True)

    h = block.find(["h1","h2","h3","h4"])
    artist = h.get_text(strip=True) if h else ""
    if not artist or len(artist) < 3:
        return None

    # Date
    date_m = re.search(
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if not date_m:
        return None

    from utils import clean_date, is_future
    date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {date_m.group(3)}")
    if not is_future(date_str):
        return None

    time_m  = re.search(r"(\d{1,2}[.:]\d{2})\s*(pm|am)?", text, re.IGNORECASE)
    price_m = re.search(r"£(\d+)", text)
    link    = block.find("a", href=True)
    href    = link["href"] if link else ""
    ticket_url = href if href.startswith("http") else (BASE_URL + href if href else JAZZ_URL)

    return gig(
        artist_name=artist,
        venue_name=VENUE,
        date=date_str,
        start_time=time_m.group(0) if time_m else "",
        price_from=f"£{price_m.group(1)}" if price_m else "",
        ticket_url=ticket_url,
        source_url=JAZZ_URL,
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags="Concert Hall",
        genre_tier1="Contemporary Jazz",
        venue_tier="2",
        editors_pick=True,  # All Wigmore Hall jazz is editor's pick quality
    )


def _parse_text(text) -> list:
    """Fallback text parser if event blocks not found."""
    results = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    from utils import clean_date, is_future

    i = 0
    while i < len(lines):
        # Look for date patterns
        date_m = re.search(
            r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
            lines[i], re.IGNORECASE
        )
        if date_m:
            date_str = clean_date(
                f"{date_m.group(2)} {date_m.group(3)} {date_m.group(4)}"
            )
            if is_future(date_str) and i + 1 < len(lines):
                artist = lines[i + 1]
                if len(artist) > 3 and not re.match(r"^\d", artist):
                    results.append(gig(
                        artist_name=artist,
                        venue_name=VENUE,
                        date=date_str,
                        ticket_url=JAZZ_URL,
                        source_url=JAZZ_URL,
                        zone=ZONE,
                        neighbourhood=HOOD,
                        format_tags="Concert Hall",
                        genre_tier1="Contemporary Jazz",
                        venue_tier="2",
                        editors_pick=True,
                    ))
        i += 1

    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Wigmore Hall jazz concerts")


if __name__ == "__main__":
    run()
