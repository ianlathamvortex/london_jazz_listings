"""
scraper_bluenotelondon.py — Blue Note London, 42-49 St Martin's Lane, Covent Garden
Source: https://www.bluenotejazz.com/london/shows/
Opened September 2026. Clean HTML — no Playwright needed.
Two shows per night (7pm and 9:30pm) — each scraped as separate gig.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "Blue Note London"
ZONE     = "Central"
HOOD     = "Covent Garden"
BASE_URL = "https://www.bluenotejazz.com/london"
SHOWS    = f"{BASE_URL}/shows/"

MONTH_MAP = {
    "jan":"January","feb":"February","mar":"March","apr":"April",
    "may":"May","jun":"June","jul":"July","aug":"August",
    "sep":"September","oct":"October","nov":"November","dec":"December"
}


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    soup = fetch(SHOWS)
    if not soup:
        return []

    results = []

    # Each event block: h2 with artist name, date range, showtimes list
    event_blocks = (
        soup.select("div.show-item") or
        soup.select("div[class*='show']") or
        soup.select("li[class*='show']") or
        []
    )

    if not event_blocks:
        # Fallback: parse the listing directly
        results = _parse_listing(soup)
    else:
        for block in event_blocks:
            results.extend(_parse_block(block))

    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r["gig_id"] not in seen:
            unique.append(r)
            seen.add(r["gig_id"])

    print(f"  Found {len(unique)} future Blue Note London shows")
    return unique


def _parse_listing(soup) -> list:
    """Parse the full listing page."""
    results = []
    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Find show links — each show has a URL pattern /london/tm-event/
    event_links = soup.select("a[href*='/tm-event/']")
    seen_urls = set()

    for link in event_links:
        href = link.get("href","")
        if not href or href in seen_urls:
            continue
        seen_urls.add(href)

        # Get h2 within same container
        parent = link.parent
        for _ in range(4):
            if parent is None:
                break
            h2 = parent.find("h2")
            if h2:
                break
            parent = parent.parent

        artist = h2.get_text(strip=True) if h2 else link.get_text(strip=True)
        if not artist or len(artist) < 2:
            continue

        # Find showtime entries for this event
        container = parent
        for _ in range(3):
            if container is None:
                break
            showtime_items = container.select("li") or container.select("[class*='showtime']")
            if showtime_items:
                break
            container = container.parent

        for item in (showtime_items if container else []):
            item_text = item.get_text(separator=" ", strip=True)

            # Parse: "Wed, Sep 23 7:00 PM (Doors 5:00 PM) buy tickets"
            date_m = re.search(
                r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+"
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
                r"(\d{1,2})",
                item_text, re.IGNORECASE
            )
            time_m = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM))", item_text, re.IGNORECASE)

            if not date_m or not time_m:
                continue

            month = MONTH_MAP.get(date_m.group(2).lower()[:3], date_m.group(2))
            year = "2026"  # default; update if year appears in text
            year_m = re.search(r"\b(202[6-9]|20[3-9]\d)\b", item_text)
            if year_m:
                year = year_m.group(1)

            date_str = clean_date(f"{date_m.group(3)} {month} {year}")
            if not is_future(date_str):
                continue

            # Ticket link
            ticket_link = item.find("a", href=True)
            ticket_url = ticket_link["href"] if ticket_link else SHOWS

            start_time = time_m.group(1).strip()
            sold_out = "sold out" in item_text.lower()

            suffix = "-late" if "9" in start_time else "-early"
            import re as _re
            gig_id = _re.sub(r"[^a-z0-9]+", "-",
                             f"{artist.lower()}{suffix}-blue-note-london-{date_str}").strip("-")[:80]

            results.append({
                "gig_id": gig_id,
                "date": date_str,
                "start_time": start_time,
                "doors_time": "",
                "artist_name": artist,
                "venue_name": VENUE,
                "venue_tier": "2",
                "stage": "",
                "zone": ZONE,
                "neighbourhood": HOOD,
                "nearest_tube": "Leicester Square",
                "ticket_url": ticket_url,
                "price_from": "Sold out" if sold_out else "",
                "price_full_text": "",
                "genre_tier1": "Contemporary Jazz",
                "genre_tier2": "",
                "format_tags": "Jazz Club",
                "description": "",
                "description_verified": False,
                "description_source": "",
                "special_occasion": "",
                "editors_pick": True,
                "hidden": False,
                "source_url": SHOWS,
                "date_scraped": "",
                "last_updated": "",
                "verified": "Yes",
                "scraper_notes": "Blue Note London"
            })

    return results


def _parse_block(block) -> list:
    from utils import clean_date, is_future
    results = []
    h2 = block.find("h2")
    artist = h2.get_text(strip=True) if h2 else ""
    if not artist:
        return []

    for item in block.select("li"):
        item_text = item.get_text(separator=" ", strip=True)
        date_m = re.search(
            r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})",
            item_text, re.IGNORECASE
        )
        time_m = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM))", item_text, re.IGNORECASE)
        if not date_m or not time_m:
            continue

        month = MONTH_MAP.get(date_m.group(2).lower()[:3], date_m.group(2))
        date_str = clean_date(f"{date_m.group(3)} {month} 2026")
        if not is_future(date_str):
            continue

        ticket_link = item.find("a", href=True)
        ticket_url = ticket_link["href"] if ticket_link else SHOWS
        start_time = time_m.group(1).strip()
        sold_out = "sold out" in item_text.lower()
        suffix = "-late" if "9" in start_time else "-early"
        gig_id = re.sub(r"[^a-z0-9]+", "-",
                        f"{artist.lower()}{suffix}-blue-note-london-{date_str}").strip("-")[:80]

        results.append(gig(
            artist_name=artist,
            venue_name=VENUE,
            date=date_str,
            start_time=start_time,
            ticket_url=ticket_url,
            source_url=SHOWS,
            zone=ZONE,
            neighbourhood=HOOD,
            format_tags="Jazz Club",
            genre_tier1="Contemporary Jazz",
            venue_tier="2",
            editors_pick=True,
        ))
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Blue Note London gigs")


if __name__ == "__main__":
    run()
