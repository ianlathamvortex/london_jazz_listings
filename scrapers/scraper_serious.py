"""
scraper_serious.py — Serious Promotions
Source: https://serious.org.uk/whats-on/upcoming-events
Covers: Barbican, Cadogan Hall, Union Chapel, Theatre Royal Drury Lane,
        Royal Albert Hall, EartH, Jazz Cafe, KOKO and more
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

BASE_URL = "https://serious.org.uk"
EVENTS   = f"{BASE_URL}/whats-on/upcoming-events"

# Map Serious venue names to our schema
VENUE_MAP = {
    "barbican":            ("Barbican Centre",         "Central", "Barbican / City",           "Concert Hall", "2"),
    "cadogan":             ("Cadogan Hall",             "Central", "Whitehall / Westminster",   "Concert Hall", "2"),
    "union chapel":        ("Union Chapel",             "North",   "Islington / Angel",         "Concert Hall", "2"),
    "theatre royal":       ("Theatre Royal Drury Lane", "Central", "Covent Garden",             "Concert Hall", "2"),
    "royal albert":        ("Royal Albert Hall",        "Central", "Piccadilly",                "Concert Hall", "2"),
    "earth":               ("EartH Theatre",            "North",   "Dalston",                   "Concert Hall", "2"),
    "jazz cafe":           ("Jazz Café",                "North",   "Camden",                    "Standing / Gig","1"),
    "koko":                ("KOKO",                     "North",   "Camden",                    "Concert Hall", "2"),
    "southbank":           ("Southbank Centre",         "Central", "Barbican / City",           "Concert Hall", "2"),
    "south bank":          ("Southbank Centre",         "Central", "Barbican / City",           "Concert Hall", "2"),
    "kings place":         ("King's Place",             "Central", "Barbican / City",           "Concert Hall", "2"),
    "king's place":        ("King's Place",             "Central", "Barbican / City",           "Concert Hall", "2"),
    "ica":                 ("ICA",                      "Central", "Whitehall / Westminster",   "Concert Hall", "2"),
    "thamesmead":          ("Thamesmead Festival",      "South East","Greenwich",               "Outdoor",      "2"),
}


def scrape() -> list:
    print("Scraping Serious Promotions...")
    soup = fetch(EVENTS)
    if not soup:
        return []

    results = []

    # Serious events page — each event is a card/article
    event_blocks = (
        soup.select("article.event") or
        soup.select("div.event-item") or
        soup.select("div[class*='event']") or
        soup.select("li.event") or
        []
    )

    if event_blocks:
        for block in event_blocks:
            result = _parse_block(block)
            if result and is_future(result["date"]):
                results.append(result)
    else:
        # Fallback: find all event links
        links = soup.select(f"a[href*='{BASE_URL}/whats-on/'], a[href*='/event/']")
        seen = set()
        for link in links:
            href = link.get("href","")
            if not href or href in seen or href == EVENTS:
                continue
            seen.add(href)
            full_url = href if href.startswith("http") else BASE_URL + href
            result = _scrape_event_page(full_url)
            if result and is_future(result["date"]):
                results.append(result)

    print(f"  Found {len(results)} future Serious gigs")
    return results


def _parse_block(block) -> dict | None:
    text = block.get_text(separator=" ", strip=True)

    # Artist/title
    h = block.find(["h1","h2","h3","h4"])
    artist = h.get_text(strip=True) if h else ""
    if not artist:
        return None

    # Date
    date_m = re.search(
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"(?:\s+(\d{4}))?",
        text, re.IGNORECASE
    )
    if not date_m:
        return None
    year = date_m.group(3) or "2026"
    date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")

    # Venue
    venue_name, zone, hood, fmt, tier = _identify_venue(text)

    # Link
    link = block.find("a", href=True)
    href = link["href"] if link else ""
    ticket_url = href if href.startswith("http") else (BASE_URL + href if href else EVENTS)

    # Price
    price_m = re.search(r"£(\d+)", text)
    price = f"£{price_m.group(1)}" if price_m else ""

    return gig(
        artist_name=artist,
        venue_name=venue_name,
        date=date_str,
        price_from=price,
        ticket_url=ticket_url,
        source_url=EVENTS,
        zone=zone,
        neighbourhood=hood,
        format_tags=fmt,
        genre_tier1="Contemporary Jazz",
        venue_tier=tier,
    )


def _scrape_event_page(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    text = soup.get_text(separator=" ", strip=True)

    h1 = soup.find("h1")
    artist = h1.get_text(strip=True) if h1 else ""
    if not artist:
        return None

    date_m = re.search(
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"(?:\s+(\d{4}))?",
        text, re.IGNORECASE
    )
    if not date_m:
        return None
    year = date_m.group(3) or "2026"
    date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")

    time_m = re.search(r"(\d{1,2}[:.]\d{2})\s*(pm|am)", text, re.IGNORECASE)
    start_time = time_m.group(0) if time_m else ""

    price_m = re.search(r"£(\d+)", text)
    price = f"£{price_m.group(1)}" if price_m else ""

    venue_name, zone, hood, fmt, tier = _identify_venue(text)

    return gig(
        artist_name=artist,
        venue_name=venue_name,
        date=date_str,
        start_time=start_time,
        price_from=price,
        ticket_url=url,
        source_url=url,
        zone=zone,
        neighbourhood=hood,
        format_tags=fmt,
        genre_tier1="Contemporary Jazz",
        venue_tier=tier,
    )


def _identify_venue(text: str) -> tuple:
    """Identify venue from event text."""
    text_lower = text.lower()
    for keyword, info in VENUE_MAP.items():
        if keyword in text_lower:
            return info
    return ("London Venue", "Central", "London", "Concert Hall", "2")


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Serious gigs")


if __name__ == "__main__":
    run()
