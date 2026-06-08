"""
scraper_vortex.py — Vortex Jazz Club, Dalston
Source: https://www.vortexjazz.co.uk/events/
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "Vortex Jazz Club"
ZONE     = "North"
HOOD     = "Dalston"
BASE_URL = "https://www.vortexjazz.co.uk"
EVENTS   = f"{BASE_URL}/events/"

# Scrape next 90 days
DAYS_AHEAD = 90


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    results = []

    # Vortex uses date-based URLs: /events/YYYY-MM-DD/
    today = datetime.now()
    seen_ids = set()

    for i in range(DAYS_AHEAD):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        url = f"{BASE_URL}/events/{date_str}/"

        day_gigs = _scrape_day(url, date_str)
        for g in day_gigs:
            if g["gig_id"] not in seen_ids:
                results.append(g)
                seen_ids.add(g["gig_id"])

    print(f"  Found {len(results)} future gigs")
    return results


def _scrape_day(url: str, date_str: str) -> list:
    """Scrape a single day page from the Vortex calendar."""
    soup = fetch(url)
    if not soup:
        return []

    results = []

    # Vortex event pages list events for that day
    # Each event has artist name, time and price
    event_blocks = (
        soup.select("div.tribe-event") or
        soup.select("article.type-tribe_events") or
        soup.select("div.event-listing") or
        soup.select("h2.tribe-events-list-event-title") or
        []
    )

    if not event_blocks:
        # Try parsing the page text
        text = soup.get_text(separator="\n", strip=True)
        if "No events" in text or "404" in soup.title.string if soup.title else False:
            return []

        # Look for event titles
        titles = soup.find_all(["h1","h2","h3"],
                               string=re.compile(r".{5,}"))
        for title in titles:
            artist = title.get_text(strip=True)
            if _is_valid_artist(artist):
                # Get surrounding context for time/price
                parent_text = title.parent.get_text(separator=" ", strip=True) if title.parent else ""
                time_m = re.search(r"(\d{1,2}[:.]\d{2})\s*(pm|am)?", parent_text, re.I)
                price_m = re.search(r"£(\d+)", parent_text)

                link = title.find("a") or title.parent.find("a") if title.parent else None
                ticket_url = BASE_URL + link["href"] if link and link.get("href","").startswith("/") else (link["href"] if link else url)

                results.append(gig(
                    artist_name=artist,
                    venue_name=VENUE,
                    date=date_str,
                    start_time=time_m.group(0) if time_m else "19:45",
                    price_from=f"£{price_m.group(1)}" if price_m else "",
                    ticket_url=ticket_url,
                    source_url=url,
                    zone=ZONE,
                    neighbourhood=HOOD,
                    format_tags="Standing / Gig",
                    genre_tier1="Contemporary Jazz",
                ))
        return results

    for block in event_blocks:
        try:
            result = _parse_event_block(block, date_str, url)
            if result:
                results.append(result)
        except Exception as e:
            print(f"  Parse error on {date_str}: {e}")

    return results


def _parse_event_block(block, date_str: str, source_url: str) -> dict | None:
    # Artist name
    title_el = block.find(["h1","h2","h3","h4"]) or block.find(class_=re.compile("title"))
    if not title_el:
        return None
    artist = title_el.get_text(strip=True)
    if not _is_valid_artist(artist):
        return None

    text = block.get_text(separator=" ", strip=True)

    # Time
    time_m = re.search(r"(\d{1,2}[:.]\d{2})\s*(pm|am)?", text, re.I)
    start_time = time_m.group(0) if time_m else "19:45"

    # Price
    price_m = re.search(r"£(\d+)", text)
    price = f"£{price_m.group(1)}" if price_m else ""

    # Ticket link
    link = block.find("a", href=True)
    if link:
        href = link["href"]
        ticket_url = BASE_URL + href if href.startswith("/") else href
    else:
        ticket_url = source_url

    # Is it a downstairs/upstairs show?
    stage = ""
    if "downstairs" in text.lower():
        stage = "Downstairs"
    elif "upstairs" in text.lower():
        stage = "Upstairs"

    # Special occasion
    special = ""
    if "album launch" in text.lower():
        special = "Album launch"
    elif "album release" in text.lower():
        special = "Album launch"

    return gig(
        artist_name=artist,
        venue_name=VENUE,
        date=date_str,
        start_time=start_time,
        price_from=price,
        ticket_url=ticket_url,
        source_url=source_url,
        stage=stage,
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags="Standing / Gig",
        genre_tier1="Contemporary Jazz",
        special_occasion=special,
    )


def _is_valid_artist(name: str) -> bool:
    """Filter out navigation elements and boilerplate text."""
    skip = {"vortex jazz club", "events", "home", "about", "contact",
            "login", "book online", "members", "next", "previous",
            "back to site", "export"}
    if not name or len(name) < 3 or len(name) > 100:
        return False
    return name.lower() not in skip


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Vortex gigs")


if __name__ == "__main__":
    run()
