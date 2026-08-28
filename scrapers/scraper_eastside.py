"""
scraper_eastside.py — East Side Jazz Club, Leytonstone
Source: https://wegottickets.com/EastSideJazzClub/
Their own website is not updated — WeGotTickets is the live source.
Every Tuesday evening at Leytonstone Social Club.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "East Side Jazz Club"
ZONE     = "East"
HOOD     = "Leytonstone"
SOURCE   = "https://wegottickets.com/EastSideJazzClub/"
BASE_WGT = "https://wegottickets.com"


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    soup = fetch(SOURCE)
    if not soup:
        return []

    results = []
    event_links = soup.select("a[href*='/f/']")
    seen = set()

    for link in event_links:
        href = link.get("href", "")
        if not href or href in seen:
            continue
        seen.add(href)

        parent = link
        for _ in range(5):
            parent = parent.parent
            if parent and parent.name in ("div", "section", "article", "li", "td"):
                break

        if not parent:
            continue

        text = parent.get_text(separator=" ", strip=True)
        if "not currently available" in text.lower():
            continue

        h = parent.find("h2")
        artist = h.get_text(strip=True) if h else link.get_text(strip=True)
        if not artist or len(artist) < 3:
            continue

        date_m = re.search(
            r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
            r"(\d{1,2})\w*\s+"
            r"(January|February|March|April|May|June|July|August|"
            r"September|October|November|December)[,\s]+(\d{4})",
            text, re.IGNORECASE
        )
        if not date_m:
            continue

        date_str = clean_date(f"{date_m.group(2)} {date_m.group(3)} {date_m.group(4)}")
        if not is_future(date_str):
            continue

        ticket_url = href if href.startswith("http") else BASE_WGT + href

        special = ""
        name_lower = artist.lower()
        if "tribute" in name_lower:
            special = "Tribute concert"
        elif "efg" in name_lower or "london jazz festival" in name_lower:
            special = "EFG London Jazz Festival"
        elif "album launch" in name_lower:
            special = "Album launch"

        results.append(gig(
            artist_name=artist,
            venue_name=VENUE,
            date=date_str,
            start_time="8:30pm",
            ticket_url=ticket_url,
            source_url=SOURCE,
            zone=ZONE,
            neighbourhood=HOOD,
            format_tags="Jazz Club",
            genre_tier1="Contemporary Jazz",
            venue_tier="1",
            special_occasion=special,
        ))

    print(f"  Found {len(results)} future East Side Jazz Club gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new East Side Jazz Club gigs")


if __name__ == "__main__":
    run()
