"""
scraper_jazzvespers.py — Jazz Vespers series, American International Church
Source: https://amchurch.co.uk/mec-category/jazzvespers/

Monthly (usually 4th Wednesday) jazz service at the American International
Church, Tottenham Court Road. Tickets are sold via Eventbrite, but Eventbrite
itself is JS-rendered with no reliable server-side event list to scrape
(organizer profile page loads events client-side only). The church's own
site runs a WordPress "Modern Events Calendar" (MEC) plugin with a clean,
server-rendered category page listing every upcoming date — far more
reliable, and it's the canonical source anyway since the church runs the
series.

All Jazz Vespers events are free to attend (confirmed via UK Jazz News
coverage and the absence of any price info across event pages).
"""

import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, is_future

VENUE     = "American International Church"
ZONE      = "Central"
HOOD      = "Fitzrovia"
BASE_URL  = "https://amchurch.co.uk"
CATEGORY_URL = f"{BASE_URL}/mec-category/jazzvespers/"


def _month_to_num(mon: str) -> str:
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    return months.get(mon.lower()[:3], "01")


def _find_event_links() -> list[str]:
    soup = fetch(CATEGORY_URL)
    if not soup:
        return []
    links = set()
    for a in soup.select("a[href*='/events/']"):
        href = a.get("href", "")
        if "/events/" in href and href.rstrip("/") != f"{BASE_URL}/events":
            links.add(href.split("?")[0])
    return sorted(links)


def _scrape_event_page(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    text = soup.get_text(separator=" | ", strip=True)

    # Title
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        return None

    # Description — meta og:description carries the actual artist/programme
    # info most reliably (page body repeats it inline with no clean wrapper)
    desc = ""
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        desc = og_desc["content"].strip()

    # Date — "### Date | Sep 23 2026" pattern in the rendered text
    date_m = re.search(
        r"Date\s*\|\s*"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{1,2})\s+(\d{4})",
        text, re.IGNORECASE
    )
    if not date_m:
        return None
    month, day, year = date_m.group(1), date_m.group(2), date_m.group(3)
    date_str = f"{year}-{_month_to_num(month)}-{int(day):02d}"
    if not is_future(date_str):
        return None

    # Time — "### Time | 6:30 pm - 7:30 pm"
    time_m = re.search(r"Time\s*\|\s*(\d{1,2}:\d{2}\s*[ap]m)", text, re.IGNORECASE)
    start_time = time_m.group(1).replace(":", ".").lower() if time_m else "6.30pm"

    # Artist name — pull from description if it names a specific act,
    # otherwise fall back to the page title itself ("Jazz Vespers")
    artist = title
    artist_m = re.search(r"featuring ([A-Z][\w .'\-]+?)(?:\s+will|\s+perform|\.|$)", desc)
    if artist_m:
        artist = artist_m.group(1).strip()

    return gig(
        artist_name=artist,
        venue_name=VENUE,
        date=date_str,
        start_time=start_time,
        price_from="Free",
        ticket_url=url,
        source_url=CATEGORY_URL,
        description=desc[:400],
        special_occasion="Jazz Vespers" if artist != title else "",
        genre_tier1="Contemporary Jazz",
        format_tags="Jazz Club",
        zone=ZONE,
        neighbourhood=HOOD,
        venue_tier="1",
    )


def scrape() -> list:
    print(f"Scraping Jazz Vespers ({VENUE})...")
    links = _find_event_links()
    results = []
    for url in links:
        g = _scrape_event_page(url)
        if g:
            results.append(g)
    print(f"  Found {len(results)} future Jazz Vespers gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No Jazz Vespers gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Jazz Vespers gigs")


if __name__ == "__main__":
    run()
