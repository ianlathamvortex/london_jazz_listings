"""
scraper_highamsparkjazz.py — Highams Park Jazz Club
Source: https://highamsparkjazzclub.com/session-dates
Fortnightly Sundays — alternates between ticketed gigs and jam sessions.
Jams go to jam_sessions.json (as one-off entries with the featured guest).
Gigs go to gigs.json.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, is_future

VENUE    = "Highams Park Jazz Club"
ZONE     = "East"
HOOD     = "Highams Park"
TUBE     = "Highams Park Overground"
URL      = "https://highamsparkjazzclub.com/session-dates"
TICKETS  = "https://highamsparkjazzclub.com/eventstickets"


def scrape():
    print(f"Scraping {VENUE}...")
    soup = fetch(URL)
    if not soup:
        return [], []

    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    gigs_out = []
    jams_out = []
    current_date = None
    current_title = None

    for i, line in enumerate(lines):
        # Date pattern: dd.mm.yyyy
        date_m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", line)
        if date_m:
            current_date = f"{date_m.group(3)}-{date_m.group(2)}-{date_m.group(1)}"
            current_title = None
            continue

        if not current_date or not is_future(current_date):
            continue

        # Skip separator lines
        if re.match(r"^_+$", line) or line.startswith("=="):
            continue

        # Title line — first non-empty line after date
        if current_title is None and len(line) > 3:
            current_title = line
            is_jam = "jam session" in line.lower()

            if is_jam:
                # Featured guest is usually after "feat"
                guest_m = re.search(r"feat\.?\s+(.+)", line, re.IGNORECASE)
                guest = guest_m.group(1).strip() if guest_m else ""

                jams_out.append({
                    "session_id": f"highams-park-jam-{current_date}",
                    "session_name": f"Jam Session feat. {guest}" if guest else "Jam Session",
                    "venue_name": VENUE,
                    "address": "All Saints Church, Church Avenue",
                    "postcode": "E4 9QZ",
                    "zone": ZONE,
                    "neighbourhood": HOOD,
                    "nearest_tube": TUBE,
                    "day_of_week": "Sunday",
                    "frequency": f"One-off ({current_date})",
                    "start_time": "17:00",
                    "end_time": "20:00",
                    "free_or_paid": "Paid",
                    "price_notes": "Check website",
                    "booking_url": TICKETS,
                    "description": f"Jam session at Highams Park Jazz Club featuring {guest}. House rhythm section: Soner Ersen (piano), Dave Manington (bass), Eric Ford (drums)." if guest else "Jam session with the house rhythm section.",
                    "genre_tier1": "Contemporary Jazz",
                    "open_to_all": True,
                    "editors_pick": False,
                    "hidden": False,
                    "last_verified": current_date,
                    "source_url": URL
                })
            else:
                gigs_out.append(gig(
                    artist_name=current_title,
                    venue_name=VENUE,
                    date=current_date,
                    start_time="17:00",
                    ticket_url=TICKETS,
                    source_url=URL,
                    zone=ZONE,
                    neighbourhood=HOOD,
                    format_tags="Jazz Club",
                    genre_tier1="Contemporary Jazz",
                    venue_tier="1",
                ))

    print(f"  Found {len(gigs_out)} gigs, {len(jams_out)} jam sessions")
    return gigs_out, jams_out


def run():
    new_gigs, new_jams = scrape()

    if new_gigs:
        existing = load("gigs")
        merged, added = merge_gigs(existing, new_gigs)
        save("gigs", merged)
        print(f"  Added {added} new Highams Park gigs")

    if new_jams:
        existing_jams = load("jam_sessions")
        existing_ids = {j.get("session_id","") for j in existing_jams}
        added = 0
        for j in new_jams:
            if j["session_id"] not in existing_ids:
                existing_jams.append(j)
                added += 1
        save("jam_sessions", existing_jams)
        print(f"  Added {added} new Highams Park jam sessions")


if __name__ == "__main__":
    run()
