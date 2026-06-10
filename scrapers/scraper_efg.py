"""
scraper_efg.py — EFG London Jazz Festival
Source: https://efglondonjazzfestival.org.uk/whats-on
Runs in November. Server-side rendered — no Playwright needed.
Festival runs 13-22 November annually.
Only picks up London-venue gigs (filters out Worthing, Cheltenham etc).
"""

import re
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup
from utils import gig, load, save, merge_gigs, clean_date, is_future

BASE_URL   = "https://efglondonjazzfestival.org.uk"
EVENTS_URL = f"{BASE_URL}/whats-on"
SOURCE_URL = EVENTS_URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
}

# Map EFG venue names → our schema
VENUE_MAP = {
    "barbican":              ("Barbican",             "Central",    "Barbican",         "1", "Concert Hall"),
    "cadogan":               ("Cadogan Hall",         "Central",    "Chelsea",          "1", "Concert Hall"),
    "royal festival hall":   ("Royal Festival Hall",  "Central",    "South Bank",       "1", "Concert Hall"),
    "efg london jazz festival south bank centre / royal festival hall":
                             ("Royal Festival Hall",  "Central",    "South Bank",       "1", "Concert Hall"),
    "southbank centre / royal festival hall":
                             ("Royal Festival Hall",  "Central",    "South Bank",       "1", "Concert Hall"),
    "kings place":           ("King's Place",        "Central",    "King's Cross",    "1", "Concert Hall"),
    "kings place (hall one)":("King's Place",        "Central",    "King's Cross",    "1", "Concert Hall"),
    "wigmore":               ("Wigmore Hall",         "Central",    "Marylebone",       "1", "Concert Hall"),
    "royal albert":          ("Royal Albert Hall",    "West",       "South Kensington", "1", "Concert Hall"),
    "union chapel":          ("Union Chapel",         "North",      "Islington",        "1", "Concert Hall"),
    "earth":                 ("EartH Theatre",        "North",      "Hackney",          "1", "Concert Hall"),
    "ronnie scott":          ("Ronnie Scott's",      "Central",    "Soho",             "1", "Jazz Club"),
    "vortex":                ("Vortex Jazz Club",     "North",      "Dalston",          "1", "Jazz Club"),
    "jazz cafe":             ("Jazz Café",            "North",      "Camden",           "1", "Standing / Gig"),
    "milton court":          ("Milton Court",         "Central",    "Barbican",         "1", "Concert Hall"),
    "koko":                  ("KOKO",                 "North",      "Camden",           "2", "Standing / Gig"),
    "stone nest":            ("Stone Nest",           "Central",    "Soho",             "2", "Standing / Gig"),
    "jazz cafe":             ("Jazz Café Camden",     "North",      "Camden",           "1", "Standing / Gig"),
    "purcell room":          ("Queen Elizabeth Hall", "Central",    "South Bank",       "1", "Concert Hall"),
    "southbank centre / purcell room":
                             ("Queen Elizabeth Hall", "Central",    "South Bank",       "1", "Concert Hall"),
    "southbank centre":      ("Royal Festival Hall",  "Central",    "South Bank",       "1", "Concert Hall"),
    "cecill sharp house":    ("Cecil Sharp House",    "North",      "Camden",           "2", "Standing / Gig"),
    "british airways arc":   ("British Airways ARC",  "East",       "Royal Docks",      "2", "Standing / Gig"),
}

# Venues outside London — skip these
SKIP_VENUES = {
    "worthing", "cheltenham", "gateshead", "birmingham", "manchester",
    "glasgow", "edinburgh", "bristol", "cardiff", "leeds", "liverpool",
}


def _lookup_venue(venue_raw: str):
    """Return (venue_name, zone, neighbourhood, tier, format) or None."""
    vl = venue_raw.lower().strip()
    # Skip non-London
    if any(s in vl for s in SKIP_VENUES):
        return None
    # Exact key match first
    if vl in VENUE_MAP:
        return VENUE_MAP[vl]
    # Partial match
    for key, val in VENUE_MAP.items():
        if key in vl or vl in key:
            return val
    # Unknown London venue — include with generic fields
    return (venue_raw.strip(), "Central", "London", "2", "Concert Hall")


def _fetch_page(url: str) -> BeautifulSoup | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return BeautifulSoup(r.read(), "html.parser")
    except Exception as e:
        print(f"  Failed to fetch {url}: {e}")
        return None


def _parse_date(date_str: str) -> str | None:
    """Parse 'Fri 13 Nov 2026' → '2026-11-13'"""
    import re
    from datetime import datetime
    date_str = re.sub(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*", "", date_str.strip(), flags=re.I)
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def scrape() -> list:
    print("Scraping EFG London Jazz Festival...")
    results = []
    seen_ids = set()

    # The site shows 24 events by default; try requesting more
    for url in [EVENTS_URL, f"{EVENTS_URL}?perPage=100"]:
        soup = _fetch_page(url)
        if not soup:
            continue

        # Events are in <a> tags containing artist name, date, venue
        # Pattern: link text = "{Artist Name}\n{Day DD Mon YYYY}\n{Venue}"
        event_links = soup.find_all("a", href=re.compile(r"/events/"))

        for link in event_links:
            href = link.get("href", "")
            if not href or href == f"{BASE_URL}/events":
                continue

            full_url = href if href.startswith("http") else BASE_URL + href
            text = link.get_text(separator="\n", strip=True)
            lines = [l.strip() for l in text.split("\n") if l.strip()]

            if len(lines) < 2:
                continue

            # Lines: [artist_name, date, venue] or [artist_name, date+venue]
            artist = lines[0]
            if not artist or len(artist) < 3:
                continue
            if "Read more" in artist or artist.lower() in ("next page", "previous page"):
                continue

            # Find date line
            date_str = ""
            venue_raw = ""
            for i, line in enumerate(lines[1:], 1):
                date_m = re.search(
                    r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
                    line, re.I
                )
                if date_m and not date_str:
                    date_str = _parse_date(line)
                elif not venue_raw and len(line) > 2:
                    venue_raw = line

            if not date_str or not is_future(date_str):
                continue

            venue_info = _lookup_venue(venue_raw) if venue_raw else None
            if venue_info is None:
                continue  # outside London

            venue_name, zone, hood, tier, fmt = venue_info

            g = gig(
                artist_name   = artist,
                venue_name    = venue_name,
                date          = date_str,
                start_time    = "",
                ticket_url    = full_url,
                source_url    = SOURCE_URL,
                zone          = zone,
                neighbourhood = hood,
                venue_tier    = tier,
                format_tags   = fmt,
                genre_tier1   = "Contemporary Jazz",
                special_occasion = "EFG London Jazz Festival",
            )
            # Auto editors_pick for major venues — EFG is curated
            g["editors_pick"] = tier == "1"

            gig_id = g["gig_id"]
            if gig_id not in seen_ids:
                results.append(g)
                seen_ids.add(gig_id)

        if results:
            break  # got results from first URL, stop

    print(f"  Found {len(results)} future EFG London gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No EFG gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new EFG London Jazz Festival gigs")


if __name__ == "__main__":
    run()
