"""
scraper_trinitylaban.py — Trinity Laban Conservatoire, Greenwich
Source: https://www.trinitylaban.ac.uk/whats-on-performance/?artform=music
Scrapes music performances — filters for jazz-relevant events.
Free entry lunchtime concerts go to free_entry, ticketed go to gigs.
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE        = "Trinity Laban"
ZONE         = "South East"
HOOD         = "Greenwich"
BASE_URL     = "https://www.trinitylaban.ac.uk"
EVENTS_URL   = f"{BASE_URL}/whats-on-performance/?artform=music"
LUNCHTIME_URL = f"{BASE_URL}/whats-on/lunchtime-concerts/"

# Jazz keywords for filtering
JAZZ_KEYWORDS = [
    "jazz", "improvisation", "improvised", "bebop", "swing", "blues",
    "saxophone", "trumpet", "big band", "ensemble", "quartet", "quintet",
    "trio", "latin", "afro", "soul", "fusion", "orchestra jazz",
    "tomorrow's warriors", "gary crosby", "john mclaughlin",
]

# Keywords that indicate NOT jazz (to filter out)
NOT_JAZZ = [
    "competition concert", "runswick competition", "rosalie coopman",
    "fidelio trio", "guitar festival", "sounding the soul",
    "new lights", "graduate school showcase",
    "symphony orchestra", "string quartet", "chamber", "opera",
    "ballet", "contemporary dance", "musical theatre", "classical guitar",
    "organ recital", "choral", "piano recital", "violin",
]


def _is_jazz_relevant(text: str) -> bool:
    """Check if an event is jazz-relevant."""
    text_lower = text.lower()
    # Explicit jazz keywords
    if any(kw in text_lower for kw in JAZZ_KEYWORDS):
        return True
    # Exclude clearly non-jazz classical events
    if any(kw in text_lower for kw in NOT_JAZZ):
        return False
    # Include student recitals and showcases by default
    # (Trinity Laban has a strong jazz programme)
    if any(kw in text_lower for kw in
           ["recital", "showcase", "concert", "performance", "lunchtime"]):
        return True
    return False


def scrape_month(month_str: str) -> list:
    """Scrape a single month page e.g. '2026-06'"""
    url = f"{BASE_URL}/whats-on-performance/?artform=music&month={month_str}"
    soup = fetch(url)
    if not soup:
        return []

    results = []

    # Trinity Laban uses standard WordPress event cards
    # Each event is an article or div with a title and date
    event_cards = (
        soup.select("article") or
        soup.select("div.event-card") or
        soup.select("div[class*='event']") or
        soup.select("li[class*='event']") or
        []
    )

    if not event_cards:
        # Fallback: find all event links
        event_links = soup.select("a[href*='/whats-on/']")
        seen = set()
        for link in event_links:
            href = link.get("href", "")
            if not href or href in seen or href == EVENTS_URL:
                continue
            if href.endswith("/whats-on/") or "page" in href:
                continue
            seen.add(href)
            full_url = href if href.startswith("http") else BASE_URL + href
            result = _scrape_event_page(full_url)
            if result and is_future(result["date"]):
                results.append(result)
        return results

    for card in event_cards:
        result = _parse_card(card)
        if result and is_future(result["date"]):
            results.append(result)

    return results


def _parse_card(card) -> dict | None:
    """Parse a Trinity Laban event card."""
    text = card.get_text(separator=" ", strip=True)

    # Filter non-jazz
    if not _is_jazz_relevant(text):
        return None

    # Title
    h = card.find(["h1", "h2", "h3", "h4"])
    title = h.get_text(strip=True) if h else ""
    if not title:
        return None

    # Date — Trinity Laban uses formats like "Fri 26 Jun 2026" or "Mon 15 – Sat 20 Jun 2026"
    date_m = re.search(
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if not date_m:
        return None

    date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {date_m.group(3)}")

    # Venue within Trinity Laban
    stage = ""
    if "king charles court" in text.lower():
        stage = "King Charles Court"
    elif "st alfege" in text.lower():
        stage = "St Alfege Church"
    elif "laban theatre" in text.lower():
        stage = "Laban Theatre"
    elif "peacock room" in text.lower():
        stage = "Peacock Room"
    elif "blackheath halls" in text.lower():
        stage = "Blackheath Halls"
        # Blackheath Halls is a separate venue
    elif "the albany" in text.lower():
        stage = "The Albany"

    # Is it free? Trinity Laban lunchtime concerts are free
    is_free = any(kw in text.lower() for kw in
                  ["free", "lunchtime concert", "free entry", "no charge"])
    price = "Free" if is_free else ""

    # Ticket link
    link = card.find("a", href=True)
    href = link["href"] if link else ""
    ticket_url = href if href.startswith("http") else (BASE_URL + href if href else EVENTS_URL)

    # Special occasion detection
    special = ""
    text_lower = text.lower()
    if "jazz orchestra" in text_lower:
        special = ""
    if "youth jazz" in text_lower:
        special = "Youth jazz celebration"
    if "album launch" in text_lower:
        special = "Album launch"

    # Category — free lunchtime concerts go to free_entry
    category = "free_entry" if is_free else "gigs"

    result = gig(
        artist_name=title,
        venue_name=VENUE,
        date=date_str,
        price_from=price,
        ticket_url=ticket_url,
        source_url=EVENTS_URL,
        stage=stage,
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags="Concert Hall",
        genre_tier1="Contemporary Jazz",
        venue_tier="2",
        special_occasion=special,
    )
    result["_category"] = category  # internal flag
    return result


def _scrape_event_page(url: str) -> dict | None:
    """Scrape individual Trinity Laban event page."""
    soup = fetch(url)
    if not soup:
        return None

    text = soup.get_text(separator=" ", strip=True)

    if not _is_jazz_relevant(text):
        return None

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        return None

    date_m = re.search(
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if not date_m:
        return None

    date_str = clean_date(
        f"{date_m.group(1)} {date_m.group(2)} {date_m.group(3)}"
    )

    time_m = re.search(r"(\d{1,2}[:.]\d{2})\s*(pm|am)", text, re.IGNORECASE)
    is_free = any(kw in text.lower() for kw in ["free", "lunchtime", "no charge"])
    price = "Free" if is_free else ""

    result = gig(
        artist_name=title,
        venue_name=VENUE,
        date=date_str,
        start_time=time_m.group(0) if time_m else "",
        price_from=price,
        ticket_url=url,
        source_url=url,
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags="Concert Hall",
        genre_tier1="Contemporary Jazz",
        venue_tier="2",
    )
    result["_category"] = "free_entry" if is_free else "gigs"
    return result


def scrape() -> tuple[list, list]:
    """Returns (ticketed_gigs, free_entry_events)"""
    print(f"Scraping {VENUE}...")

    all_results = []
    today = datetime.now()

    # Scrape next 6 months
    for i in range(6):
        month = today.replace(day=1) + timedelta(days=32 * i)
        month_str = month.strftime("%Y-%m")
        results = scrape_month(month_str)
        all_results.extend(results)
        if results:
            print(f"  {month_str}: {len(results)} events")

    # Also scrape the dedicated lunchtime concerts page
    soup = fetch(LUNCHTIME_URL)
    if soup:
        lunchtime_links = soup.select("a[href*='/whats-on/']")
        seen = set()
        for link in lunchtime_links:
            href = link.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)
            full_url = href if href.startswith("http") else BASE_URL + href
            result = _scrape_event_page(full_url)
            if result and is_future(result["date"]):
                result["_category"] = "free_entry"
                all_results.append(result)

    # Split into ticketed and free
    ticketed = [r for r in all_results
                if r.get("_category") != "free_entry" and is_future(r["date"])]
    free = [r for r in all_results
            if r.get("_category") == "free_entry" and is_future(r["date"])]

    # Clean up internal flag
    for r in ticketed + free:
        r.pop("_category", None)

    print(f"  Found {len(ticketed)} ticketed + {len(free)} free entry events")
    return ticketed, free


def run():
    ticketed, free_events = scrape()

    if ticketed:
        existing = load("gigs")
        merged, added = merge_gigs(existing, ticketed)
        save("gigs", merged)
        print(f"  Added {added} new Trinity Laban gigs")

    if free_events:
        existing = load("free_entry")
        merged, added = merge_gigs(existing, free_events)
        save("free_entry", merged)
        print(f"  Added {added} new Trinity Laban free events")

    if not ticketed and not free_events:
        print("  No events found")


if __name__ == "__main__":
    run()
