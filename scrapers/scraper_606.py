"""
scraper_606.py — 606 Club, Chelsea
Source: https://www.606club.co.uk/events/
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "606 Club"
ZONE     = "South West"
HOOD     = "Chelsea / Lots Road"
BASE_URL = "https://www.606club.co.uk"
EVENTS   = f"{BASE_URL}/events/"


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    soup = fetch(EVENTS)
    if not soup:
        return []

    results = []

    # 606 uses a calendar widget — each event has a pattern like:
    # "Mon 01st Jun - 8:00pm · Artist Name · Read More"
    # We look for the event links/blocks
    event_links = soup.select("a[href*='/event/'], a[href*='/events/']")

    seen = set()
    for link in event_links:
        href = link.get("href", "")
        if not href or href in seen or href == EVENTS:
            continue
        seen.add(href)

        full_url = BASE_URL + href if href.startswith("/") else href

        # Fetch individual event page for full details
        result = _scrape_event_page(full_url)
        if result and is_future(result["date"]):
            results.append(result)

    # Fallback: parse the calendar text directly
    if not results:
        results = _parse_calendar_text(soup)

    print(f"  Found {len(results)} future gigs")
    return results


def _parse_calendar_text(soup) -> list:
    """Parse the 606 calendar widget text directly."""
    results = []
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    current_date = None
    for line in lines:
        # Match date patterns like "Mon 01st Jun - 8:00pm" or "Thu 04th Jun - 8:00pm"
        date_match = re.match(
            r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\w*\s+"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"(?:\s+(\d{4}))?\s*[-–]\s*(\d{1,2}:\d{2}(?:am|pm)?)",
            line, re.IGNORECASE
        )
        if date_match:
            day   = date_match.group(2)
            month = date_match.group(3)
            year  = date_match.group(4) or "2026"
            time  = date_match.group(5)
            current_date = clean_date(f"{day} {month} {year}")
            current_time = time
            continue

        # Next non-empty line after a date is likely the artist
        if current_date and line and line not in ("Read More", "Lunchtime"):
            if not any(skip in line.lower() for skip in
                       ["previous", "next", "copyright", "privacy", "cookie"]):
                results.append(gig(
                    artist_name=line,
                    venue_name=VENUE,
                    date=current_date,
                    start_time=current_time if 'current_time' in dir() else "",
                    ticket_url=EVENTS,
                    source_url=EVENTS,
                    zone=ZONE,
                    neighbourhood=HOOD,
                    format_tags="Jazz Club",
                    genre_tier1="Mainstream / Swing",
                ))
                current_date = None

    return results


def _scrape_event_page(url: str) -> dict | None:
    """Scrape individual 606 event page."""
    soup = fetch(url)
    if not soup:
        return None

    text = soup.get_text(separator=" ", strip=True)

    # Artist name — h1 or h2
    h = soup.find(["h1", "h2"])
    artist = h.get_text(strip=True) if h else ""
    if not artist:
        return None

    # Date
    date_match = re.search(
        r"(\d{1,2})\w*\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"(?:\s+(\d{4}))?",
        text, re.IGNORECASE
    )
    if not date_match:
        return None
    year = date_match.group(3) or "2026"
    date_str = clean_date(f"{date_match.group(1)} {date_match.group(2)} {year}")

    # Time
    time_match = re.search(r"(\d{1,2}:\d{2})\s*(pm|am)", text, re.IGNORECASE)
    start_time = time_match.group(0) if time_match else "20:00"

    # Price — 606 usually lists music charge separately
    price_match = re.search(r"£(\d+)(?:\s*(?:music charge|per person|pp))?", text)
    price = f"£{price_match.group(1)}" if price_match else ""

    # Is it a lunchtime/brunch event?
    is_lunch = any(w in text.lower() for w in ["1:30pm", "lunchtime", "sunday lunch", "brunch"])
    fmt = "Dining" if is_lunch else "Jazz Club"
    genre = "Soul & Groove" if is_lunch else "Mainstream / Swing"

    # Special occasion detection
    special = ""
    if "album launch" in text.lower():
        special = "Album launch"
    elif "anniversary" in text.lower():
        special = "Anniversary"

    return gig(
        artist_name=artist,
        venue_name=VENUE,
        date=date_str,
        start_time=start_time,
        price_from=price,
        ticket_url=url,
        source_url=url,
        stage="Lunchtime" if is_lunch else "",
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags=fmt,
        genre_tier1=genre,
        special_occasion=special,
    )


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new 606 gigs")


if __name__ == "__main__":
    run()
