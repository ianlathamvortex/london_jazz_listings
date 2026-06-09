"""
scraper_serious.py — Serious Promotions
Source: https://serious.org.uk/whats-on/upcoming-events
Covers: Barbican, Cadogan Hall, Union Chapel, Theatre Royal Drury Lane etc.
Falls back to known hardcoded events if scraping fails.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

BASE_URL = "https://serious.org.uk"
EVENTS   = f"{BASE_URL}/whats-on/upcoming-events"

VENUE_MAP = {
    "barbican":      ("Barbican Centre",         "Central", "Barbican / City",         "Concert Hall", "2"),
    "cadogan":       ("Cadogan Hall",             "Central", "Whitehall / Westminster", "Concert Hall", "2"),
    "union chapel":  ("Union Chapel",             "North",   "Islington / Angel",       "Concert Hall", "2"),
    "theatre royal": ("Theatre Royal Drury Lane", "Central", "Covent Garden",           "Concert Hall", "2"),
    "royal albert":  ("Royal Albert Hall",        "Central", "Piccadilly",              "Concert Hall", "2"),
    "earth":         ("EartH Theatre",            "North",   "Dalston",                 "Concert Hall", "2"),
}

# Known events — updated manually each season
KNOWN_EVENTS = [
    {
        "artist_name":   "Al Di Meola",
        "event_title":   "Al Di Meola: The Guitarchitect",
        "date":          "2026-06-25",
        "start_time":    "8:00pm",
        "doors_time":    "7:30pm",
        "venue_name":    "Barbican Centre",
        "zone":          "Central",
        "neighbourhood": "Barbican / City",
        "price_from":    "£39",
        "price_full_text": "£39–£69",
        "genre_tier1":   "Fusion",
        "genre_tier2":   "Flamenco Jazz",
        "ticket_url":    "https://serious.org.uk/events/al-di-meola",
        "description":   "Five decades of music united in one refined concert experience. Di Meola's acoustic band plays 'The Guitarchitect' — sweeping multimedia visuals, the stories behind a lifetime of artistry. One of the most technically brilliant guitarists alive, still at the peak of his powers.",
        "editors_pick":  True,
    },
    {
        "artist_name":   "Terence Blanchard & Ravi Coltrane",
        "event_title":   "Miles Davis and John Coltrane at 100",
        "supporting_acts": "Julian Pollack (keys), Charles Altura (gtr), Oscar Seaton (dms), David DJ Ginyard (bass)",
        "date":          "2026-07-09",
        "start_time":    "7:30pm",
        "doors_time":    "7:00pm",
        "venue_name":    "Cadogan Hall",
        "zone":          "Central",
        "neighbourhood": "Whitehall / Westminster",
        "price_from":    "",
        "price_full_text": "Sold out",
        "genre_tier1":   "Contemporary Jazz",
        "ticket_url":    "https://serious.org.uk/events/terence-blanchard-and-ravi-coltrane-miles-davis-and-john-coltrane-at-100",
        "description":   "2026 marks 100 years since the birth of both Miles Davis and John Coltrane. Two of today's most vital bandleaders join forces — not for nostalgia but bold reimagining. Every night unique, every night unrepeatable.",
        "special_occasion": "Centenary tribute — Miles Davis & Coltrane at 100",
        "editors_pick":  True,
    },
    {
        "artist_name":   "Stacey Kent",
        "event_title":   "Stacey Kent: A Time for Love Tour",
        "supporting_acts": "Jim Tomlinson (sax), Art Hirahara (piano), Tom Hubbard (bass)",
        "date":          "2026-07-17",
        "start_time":    "7:30pm",
        "doors_time":    "7:00pm",
        "venue_name":    "Cadogan Hall",
        "zone":          "Central",
        "neighbourhood": "Whitehall / Westminster",
        "price_from":    "£39.50",
        "price_full_text": "£39.50–£59.50",
        "genre_tier1":   "Vocal & Standards",
        "genre_tier2":   "Bossa Nova",
        "ticket_url":    "https://serious.org.uk/events/stacey-kent",
        "description":   "Over a billion streams and a Grammy nomination. Kent's multi-lingual repertoire includes originals co-written by Nobel laureate Kazuo Ishiguro. New album 'A Time for Love' out this summer. Thursday sold out — Friday still available.",
        "special_occasion": "New album launch",
        "editors_pick":  True,
    },
    {
        "artist_name":   "Pat Metheny: Side-Eye III+",
        "event_title":   "Pat Metheny: Side-Eye III+ (Evening)",
        "supporting_acts": "Chris Fishman (piano/keys), Jermaine Paul (bass), Joe Dyson (drums)",
        "date":          "2026-07-18",
        "start_time":    "7:00pm",
        "doors_time":    "6:30pm",
        "venue_name":    "Barbican Centre",
        "zone":          "Central",
        "neighbourhood": "Barbican / City",
        "price_from":    "£64",
        "price_full_text": "£64–£94",
        "genre_tier1":   "Contemporary Jazz",
        "genre_tier2":   "Fusion",
        "ticket_url":    "https://serious.org.uk/events/pat-metheny-side-eye-iii",
        "description":   "Twenty Grammy wins. Metheny brings Side-Eye III+ to the Barbican — new music alongside reimagined classics, mentoring the next generation while exploring fresh sonic territory.",
        "editors_pick":  True,
    },
    {
        "artist_name":   "Pat Metheny: Side-Eye III+",
        "event_title":   "Pat Metheny: Side-Eye III+ (Matinee)",
        "supporting_acts": "Chris Fishman (piano/keys), Jermaine Paul (bass), Joe Dyson (drums)",
        "date":          "2026-07-19",
        "start_time":    "1:00pm",
        "doors_time":    "12:30pm",
        "venue_name":    "Barbican Centre",
        "zone":          "Central",
        "neighbourhood": "Barbican / City",
        "price_from":    "£64",
        "price_full_text": "£64–£94",
        "genre_tier1":   "Contemporary Jazz",
        "genre_tier2":   "Fusion",
        "ticket_url":    "https://serious.org.uk/events/pat-metheny-side-eye-iii",
        "description":   "Sunday matinee — one of three Barbican shows across the weekend.",
        "editors_pick":  False,
    },
    {
        "artist_name":   "Pat Metheny: Side-Eye III+",
        "event_title":   "Pat Metheny: Side-Eye III+ (Evening)",
        "supporting_acts": "Chris Fishman (piano/keys), Jermaine Paul (bass), Joe Dyson (drums)",
        "date":          "2026-07-19",
        "start_time":    "5:30pm",
        "doors_time":    "5:00pm",
        "venue_name":    "Barbican Centre",
        "zone":          "Central",
        "neighbourhood": "Barbican / City",
        "price_from":    "£64",
        "price_full_text": "£64–£94",
        "genre_tier1":   "Contemporary Jazz",
        "genre_tier2":   "Fusion",
        "ticket_url":    "https://serious.org.uk/events/pat-metheny-side-eye-iii",
        "description":   "Sunday evening — the final show of Metheny's Barbican weekend takeover.",
        "editors_pick":  False,
    },
]


def scrape() -> list:
    print("Scraping Serious Promotions...")
    results = []

    # Try live scraping first
    soup = fetch(EVENTS)
    if soup:
        blocks = (
            soup.select("article.event") or
            soup.select("div.event-item") or
            soup.select("div[class*='event']") or
            []
        )
        for block in blocks:
            result = _parse_block(block)
            if result and is_future(result["date"]):
                results.append(result)

    # Always include known events as fallback
    for event in KNOWN_EVENTS:
        if not is_future(event["date"]):
            continue
        g = gig(
            artist_name=event["artist_name"],
            venue_name=event["venue_name"],
            date=event["date"],
            start_time=event.get("start_time", ""),
            doors_time=event.get("doors_time", ""),
            price_from=event.get("price_from", ""),
            price_full_text=event.get("price_full_text", ""),
            ticket_url=event.get("ticket_url", ""),
            source_url="https://serious.org.uk/summer-jazz-series-2026",
            zone=event.get("zone", "Central"),
            neighbourhood=event.get("neighbourhood", ""),
            format_tags="Concert Hall",
            genre_tier1=event.get("genre_tier1", "Contemporary Jazz"),
            genre_tier2=event.get("genre_tier2", ""),
            description=event.get("description", ""),
            special_occasion=event.get("special_occasion", ""),
            venue_tier="2",
        )
        g["editors_pick"] = event.get("editors_pick", False)
        g["event_title"] = event.get("event_title", "")
        g["supporting_acts"] = event.get("supporting_acts", "")
        results.append(g)

    # Deduplicate by gig_id
    seen = set()
    unique = []
    for r in results:
        if r["gig_id"] not in seen:
            unique.append(r)
            seen.add(r["gig_id"])

    print(f"  Found {len(unique)} Serious gigs")
    return unique


def _parse_block(block) -> dict | None:
    text = block.get_text(separator=" ", strip=True)
    h = block.find(["h1","h2","h3","h4"])
    artist = h.get_text(strip=True) if h else ""
    if not artist:
        return None
    date_m = re.search(
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"(?:\s+(\d{4}))?", text, re.IGNORECASE
    )
    if not date_m:
        return None
    year = date_m.group(3) or "2026"
    date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")
    venue_name, zone, hood, fmt, tier = _identify_venue(text)
    link = block.find("a", href=True)
    href = link["href"] if link else ""
    ticket_url = href if href.startswith("http") else (BASE_URL + href if href else EVENTS)
    price_m = re.search(r"£(\d+)", text)
    return gig(
        artist_name=artist,
        venue_name=venue_name,
        date=date_str,
        price_from=f"£{price_m.group(1)}" if price_m else "",
        ticket_url=ticket_url,
        source_url=EVENTS,
        zone=zone,
        neighbourhood=hood,
        format_tags=fmt,
        genre_tier1="Contemporary Jazz",
        venue_tier=tier,
    )


def _identify_venue(text: str) -> tuple:
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
