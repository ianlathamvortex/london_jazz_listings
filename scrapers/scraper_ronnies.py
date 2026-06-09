"""
scraper_ronnies.py — Ronnie Scott's Jazz Club
503/403 blocks scrapers — uses hardcoded known residencies as fallback.
"""
import re
import sys
import requests
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, is_future

VENUE    = "Ronnie Scott's"
ZONE     = "Central"
HOOD     = "Soho"
BASE_URL = "https://www.ronniescotts.co.uk"

# Known residencies — updated each season
# These are the ONLY entries we trust from Ronnie's
KNOWN_RESIDENCIES = [
    {
        "artist_name": "Billy Cobham with the Guy Barker Big Band",
        "dates": ["2026-06-10", "2026-06-11", "2026-06-12", "2026-06-13",
                  "2026-06-14"],
        "start_time": "20:00", "stage": "Main Stage",
        "price_from": "£35", "genre_tier1": "Big Band",
        "ticket_url": "https://www.ronniescotts.co.uk/performances/view/billy-cobham",
        "editors_pick": True,
    },
    {
        "artist_name": "Benito Gonzalez Trio",
        "dates": ["2026-06-09"],
        "start_time": "20:00", "stage": "Main Stage",
        "price_from": "£30", "genre_tier1": "Contemporary Jazz",
        "ticket_url": "https://www.ronniescotts.co.uk",
        "editors_pick": True,
    },
    {
        "artist_name": "Adrien Brandeis",
        "dates": ["2026-06-11", "2026-06-12", "2026-06-13", "2026-06-14"],
        "start_time": "20:00", "stage": "Main Stage",
        "price_from": "£25", "genre_tier1": "Contemporary Jazz",
        "ticket_url": "https://www.ronniescotts.co.uk",
        "editors_pick": False,
    },
    {
        "artist_name": "Natalie Duncan",
        "dates": ["2026-06-12", "2026-06-13", "2026-06-14"],
        "start_time": "23:00", "stage": "Late Late Show",
        "price_from": "£15", "genre_tier1": "Vocal & Standards",
        "ticket_url": "https://www.ronniescotts.co.uk",
        "editors_pick": False,
    },
    {
        "artist_name": "Moyses Dos Santos",
        "dates": ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18",
                  "2026-06-19", "2026-06-20", "2026-06-21"],
        "start_time": "20:00", "stage": "Main Stage",
        "price_from": "£25", "genre_tier1": "Brazilian / MPB",
        "ticket_url": "https://www.ronniescotts.co.uk",
        "editors_pick": False,
    },
]


def scrape() -> list:
    print(f"Scraping {VENUE} (hardcoded fallback)...")
    results = []
    for residency in KNOWN_RESIDENCIES:
        for date in residency["dates"]:
            if not is_future(date):
                continue
            g = gig(
                artist_name=residency["artist_name"],
                venue_name=VENUE,
                date=date,
                start_time=residency.get("start_time", ""),
                ticket_url=residency.get("ticket_url", BASE_URL),
                source_url=BASE_URL,
                stage=residency.get("stage", ""),
                price_from=residency.get("price_from", ""),
                zone=ZONE,
                neighbourhood=HOOD,
                format_tags="Jazz Club",
                genre_tier1=residency.get("genre_tier1", "Contemporary Jazz"),
                venue_tier="1",
            )
            g["editors_pick"] = residency.get("editors_pick", False)
            results.append(g)
    print(f"  Found {len(results)} future Ronnie's gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Ronnie's gigs")


if __name__ == "__main__":
    run()
