"""
scraper_ronnies.py — Ronnie Scott's Jazz Club
Hardcoded programme — Ronnie's blocks scrapers.
Main Shows and named Upstairs shows only.
Late Late Shows are weekly residencies — excluded (they go in jam_sessions.json).
Update KNOWN_SHOWS each season from https://www.ronniescotts.co.uk/find-a-show
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, is_future

VENUE    = "Ronnie's Scott's"
ZONE     = "Central"
HOOD     = "Soho"
BASE_URL = "https://www.ronniescotts.co.uk"

# Each entry: (artist, [dates], stage, price, ticket_slug, genre, editors_pick)
KNOWN_SHOWS = [
    ("Billy Cobham with the Guy Barker Big Band",
     ["2026-06-09","2026-06-10","2026-06-11"], "Main Show", "£35",
     "billy-cobham-guy-barker", "Big Band", True),
    ("Benito Gonzalez Trio",
     ["2026-06-09"], "Upstairs at Ronnie's", "£25",
     "benito-gonzalez-trio", "Contemporary Jazz", True),
    ("Adrien Brandeis",
     ["2026-06-11"], "Upstairs at Ronnie's", "£20",
     "adrien-brandeis", "Contemporary Jazz", False),
    ("Natalie Duncan",
     ["2026-06-12"], "Upstairs at Ronnie's", "£20",
     "natalie-duncan-2", "Vocal & Standards", False),
    ("Moyses Dos Santos",
     ["2026-06-12"], "Main Show", "£25",
     "moyses-dos-santos", "Brazilian / MPB", False),
    ("Sam Greenfield",
     ["2026-06-13"], "Main Show", "£25",
     "sam-greenfield", "Contemporary Jazz", False),
    ("Phebe Edwards",
     ["2026-06-13"], "Upstairs at Ronnie's", "£15",
     "phebe-edwards", "Vocal & Standards", False),
    ("Jive Aces",
     ["2026-06-14"], "Sunday Lunch", "£30",
     "jive-aces", "Mainstream / Swing", False),
    ("Ben Sidran Quartet",
     ["2026-06-15"], "Main Show", "£25",
     "ben-sidran", "Mainstream / Swing", True),
    ("Lakecia Benjamin",
     ["2026-06-17"], "Main Show", "£30",
     "lakecia-benjamin", "Contemporary Jazz", True),
    ("Nicole Zuraitis",
     ["2026-06-30"], "Main Show", "£25",
     "nicole-zuraitis-idan-morim-dan-pugach", "Vocal & Standards", False),
    ("Kiefer",
     ["2026-07-02"], "Main Show", "£30",
     "kiefer", "Contemporary Jazz", True),
]


def scrape() -> list:
    print(f"Scraping Ronnie Scott's (hardcoded)...")
    results = []
    for artist, dates, stage, price, slug, genre, editors_pick in KNOWN_SHOWS:
        for date in dates:
            if not is_future(date):
                continue
            g = gig(
                artist_name=artist,
                venue_name="Ronnie Scott's",
                date=date,
                start_time="20:00" if stage == "Main Show" else "23:00" if "Late" in stage else "19:00",
                ticket_url=f"{BASE_URL}/find-a-show/{slug}",
                source_url=f"{BASE_URL}/find-a-show",
                stage=stage,
                price_from=price,
                zone=ZONE,
                neighbourhood=HOOD,
                format_tags="Jazz Club",
                genre_tier1=genre,
                venue_tier="1",
            )
            g["editors_pick"] = editors_pick
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
