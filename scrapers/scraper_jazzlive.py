"""
scraper_jazzlive.py — Jazzlive at The Crypt, Camberwell
Source: https://www.jazzlive.co.uk/guide.html
Weekly Friday night jazz in the crypt of St Giles Church, SE5.
Clean static HTML — very reliable to scrape.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "Jazzlive at The Crypt"
ZONE     = "South East"
HOOD     = "Camberwell"
BASE_URL = "https://www.jazzlive.co.uk"
GIG_URL  = f"{BASE_URL}/guide.html"
ADDRESS  = "St Giles Church, Camberwell Church Street, SE5 8RB"

MONTH_MAP = {
    "jan": "January", "feb": "February", "mar": "March",
    "apr": "April",   "may": "May",      "june": "June",
    "july": "July",   "aug": "August",   "sep": "September",
    "oct": "October", "nov": "November", "dec": "December",
}


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    soup = fetch(GIG_URL)
    if not soup:
        return []

    results = []

    # Each gig block has a date header like "29May 2026" and an h3 title
    # Find all date+title pairs

    # The date appears as text like "29May\n  \n2026" in a div
    # followed by an h3 with the artist name

    # Strategy: find all h3 tags (artist names) and look backwards for the date
    gig_blocks = soup.select("h3")

    for h3 in gig_blocks:
        artist = h3.get_text(strip=True)
        if not artist or len(artist) < 3:
            continue

        # Walk up the DOM to find the containing section
        parent = h3.parent
        while parent and parent.name not in ("div", "section", "article", "body"):
            parent = parent.parent

        if not parent:
            continue

        block_text = parent.get_text(separator=" ", strip=True)

        # Extract date — format is "29May 2026" or "05June 2026" etc
        date_m = re.search(
            r"(\d{1,2})\s*"
            r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
            r"June?|July?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
            r"Nov(?:ember)?|Dec(?:ember)?)"
            r"\s*(\d{4})",
            block_text, re.IGNORECASE
        )
        if not date_m:
            continue

        date_str = clean_date(
            f"{date_m.group(1)} {date_m.group(2)} {date_m.group(3)}"
        )
        if not is_future(date_str):
            continue

        # Description — paragraph text after the h3
        desc_el = h3.find_next("p")
        description = desc_el.get_text(separator=" ", strip=True)[:400] if desc_el else ""

        # Ticket link
        ticket_link = parent.find("a", href=re.compile(r"wegottickets|tickets"))
        ticket_url = ticket_link["href"] if ticket_link else GIG_URL

        # Price — usually £8–£12 for Jazzlive
        price_m = re.search(r"£(\d+)", block_text)
        price = f"£{price_m.group(1)}" if price_m else "£10"

        # Day of week for start time — Jazzlive is always Friday evenings
        # except special events
        is_sunday = "sunday" in block_text.lower()
        start_time = "19:30" if not is_sunday else "19:30"

        # Special occasion
        special = ""
        if "anniversary" in block_text.lower():
            special = "Anniversary"
        elif "album launch" in block_text.lower():
            special = "Album launch"
        elif "everywhere at once" in block_text.lower():
            special = "Everywhere at Once Festival"

        results.append(gig(
            artist_name=artist,
            venue_name=VENUE,
            date=date_str,
            start_time=start_time,
            price_from=price,
            ticket_url=ticket_url,
            source_url=GIG_URL,
            zone=ZONE,
            neighbourhood=HOOD,
            format_tags="Jazz Club",
            genre_tier1="Contemporary Jazz",
            description=description,
            special_occasion=special,
            venue_tier="1",
        ))

    print(f"  Found {len(results)} future Jazzlive gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Jazzlive gigs")


if __name__ == "__main__":
    run()
