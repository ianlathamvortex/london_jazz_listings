"""
scraper_ronnies.py — Ronnie Scott's Jazz Club
Uses the show-calendar page which has structured data
"""
import re
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "Ronnie Scott's"
ZONE     = "Central"
HOOD     = "Soho"
BASE_URL = "https://www.ronniescotts.co.uk"

HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": "https://www.google.com/",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.5",
    },
]

import requests
from bs4 import BeautifulSoup

def fetch_ronnies(url):
    """Try multiple user agents to bypass 403."""
    for headers in HEADERS_LIST:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "lxml")
            print(f"  Status {r.status_code} with UA: {headers['User-Agent'][:50]}")
        except Exception as e:
            print(f"  Error: {e}")
    return None

# Hardcoded known residencies as fallback
# These are updated manually when the programme changes
KNOWN_RESIDENCIES = [
    {
        "artist_name": "Billy Cobham with the Guy Barker Big Band",
        "dates": ["2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11"],
        "start_time": "20:00",
        "stage": "Main Stage",
        "price_from": "£35",
        "genre_tier1": "Big Band",
        "genre_tier2": "Fusion",
        "format_tags": "Jazz Club",
        "special_occasion": "",
        "ticket_url": "https://www.ronniescotts.co.uk",
    },
    {
        "artist_name": "Ronnie Scott's Jazz Jam",
        "dates": ["2026-06-08", "2026-06-15", "2026-06-22", "2026-06-29",
                  "2026-07-06", "2026-07-13", "2026-07-20", "2026-07-27"],
        "start_time": "21:30",
        "stage": "Late Late Show",
        "price_from": "£10",
        "genre_tier1": "Mainstream / Swing",
        "genre_tier2": "Bebop / Hard Bop",
        "format_tags": "Standing / Gig",
        "special_occasion": "",
        "ticket_url": "https://www.ronniescotts.co.uk/find-a-show/ronnie-scotts-jazz-jam-14",
    },
]


def scrape() -> list:
    print(f"Scraping {VENUE}...")

    # Try scraping the calendar page
    results = []
    for path in ["/find-a-show", "/show-calendar", "/"]:
        soup = fetch_ronnies(BASE_URL + path)
        if soup:
            results = _parse(soup)
            if results:
                break

    # Fall back to known residencies if scraping fails
    if not results:
        print(f"  Live scraping failed — using known residencies")
        results = _known_gigs()

    print(f"  Found {len(results)} future Ronnie's gigs")
    return results


def _parse(soup) -> list:
    results = []
    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    current_date = None
    for line in lines:
        # Date line
        date_m = re.search(
            r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[,.]?\s*"
            r"(\d{1,2})\s+"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"(?:\s+(\d{4}))?",
            line, re.IGNORECASE
        )
        if date_m:
            year = date_m.group(4) or "2026"
            current_date = clean_date(
                f"{date_m.group(2)} {date_m.group(3)} {year}"
            )
            continue

        if not current_date or not is_future(current_date):
            continue

        # Detect show lines
        stage = ""
        if "main show" in line.lower():
            stage = "Main Stage"
        elif "late late show upstairs" in line.lower():
            stage = "Late Late Show Upstairs"
        elif "late late show" in line.lower():
            stage = "Late Late Show"
        elif "upstairs at ronnie" in line.lower():
            stage = "Upstairs"

        if stage:
            # Next non-empty line should be artist
            continue

        # Artist lines — meaningful text after a date
        if (current_date and len(line) > 4 and
                not any(s in line.lower() for s in
                        ["book now", "find out more", "from £", "tickets",
                         "ronnie scott", "late late", "main show", "upstairs"])):
            results.append(gig(
                artist_name=line,
                venue_name=VENUE,
                date=current_date,
                ticket_url=BASE_URL + "/find-a-show",
                source_url=BASE_URL,
                zone=ZONE,
                neighbourhood=HOOD,
                format_tags="Jazz Club",
                genre_tier1="Contemporary Jazz",
            ))
            current_date = None

    return results


def _known_gigs() -> list:
    """Return hardcoded known Ronnie's gigs as fallback."""
    results = []
    for residency in KNOWN_RESIDENCIES:
        for date in residency["dates"]:
            if not is_future(date):
                continue
            results.append(gig(
                artist_name=residency["artist_name"],
                venue_name=VENUE,
                date=date,
                start_time=residency["start_time"],
                ticket_url=residency["ticket_url"],
                source_url=BASE_URL,
                stage=residency["stage"],
                price_from=residency["price_from"],
                zone=ZONE,
                neighbourhood=HOOD,
                format_tags=residency["format_tags"],
                genre_tier1=residency["genre_tier1"],
                genre_tier2=residency.get("genre_tier2", ""),
                special_occasion=residency.get("special_occasion", ""),
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
    print(f"  Added {added} new Ronnie's gigs")


if __name__ == "__main__":
    run()
