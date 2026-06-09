"""
scraper_cadogan.py — Cadogan Hall jazz & blues concerts
Source: https://cadoganhall.com/whats-on/genres/jazz-blues/
Clean HTML — no JavaScript rendering needed.
Includes Out to Lunch lunchtime series and evening concerts.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "Cadogan Hall"
ZONE     = "Central"
HOOD     = "Whitehall / Westminster"
BASE_URL = "https://cadoganhall.com"
JAZZ_URL = f"{BASE_URL}/whats-on/genres/jazz-blues/"

SKIP_TITLES = [
    "voices of soul", "down for the count",  # big band pop/soul, not jazz
]


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    results = []

    for page in range(1, 5):
        url = JAZZ_URL if page == 1 else f"{JAZZ_URL}page/{page}/"
        soup = fetch(url)
        if not soup:
            break

        # Each event is an article or div with h3 title and date
        event_blocks = (
            soup.select("article") or
            soup.select("div.event") or
            soup.select("div[class*='listing']") or
            []
        )

        if not event_blocks:
            break

        found = 0
        for block in event_blocks:
            result = _parse_block(block)
            if result:
                results.append(result)
                found += 1

        # Check for next page
        next_link = soup.find("a", string=re.compile(r"Next", re.I))
        if not next_link or found == 0:
            break

    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r["gig_id"] not in seen:
            unique.append(r)
            seen.add(r["gig_id"])

    print(f"  Found {len(unique)} future Cadogan Hall jazz concerts")
    return unique


def _parse_block(block) -> dict | None:
    text = block.get_text(separator=" ", strip=True)

    # Skip cancelled
    if "cancelled" in text.lower():
        return None

    # Title
    h = block.find(["h2", "h3", "h4"])
    artist = h.get_text(strip=True) if h else ""
    if not artist or len(artist) < 3:
        return None

    # Skip non-jazz
    if any(s in artist.lower() for s in SKIP_TITLES):
        return None

    # Date
    date_m = re.search(
        r"(\w+day)\s+(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if not date_m:
        return None

    date_str = clean_date(
        f"{date_m.group(2)} {date_m.group(3)} {date_m.group(4)}"
    )
    if not is_future(date_str):
        return None

    # Time
    time_m = re.search(r"(\d{1,2}(?:[.:]\d{2})?(?:am|pm))", text, re.IGNORECASE)
    start_time = time_m.group(1) if time_m else ""

    # Stage — lunchtime = Culford Room
    is_lunch = "12pm" in text or "1pm" in text or "culford" in text.lower()
    stage = "Culford Room" if is_lunch else ""

    # Ticket link
    link = block.find("a", href=re.compile(r"/whats-on/"))
    href = link["href"] if link else ""
    ticket_url = href if href.startswith("http") else (BASE_URL + href if href else JAZZ_URL)

    # Description from block
    desc_el = block.find("p")
    desc = desc_el.get_text(strip=True)[:300] if desc_el else ""

    return gig(
        artist_name=artist,
        venue_name=VENUE,
        date=date_str,
        start_time=start_time,
        ticket_url=ticket_url,
        source_url=JAZZ_URL,
        stage=stage,
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags="Concert Hall",
        genre_tier1="Contemporary Jazz",
        venue_tier="2",
        description=desc,
        editors_pick=True,
    )


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Cadogan Hall gigs")


if __name__ == "__main__":
    run()
