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

    # Each gig card is <div class="box_blog_top"> containing exactly two
    # children: <div class="blog_date"> (e.g. "03 July2026") and
    # <div class="blog_title"><h3>Artist Name</h3></div>.
    # NOTE: cards are nested (each blog_content wraps the next), NOT sibling
    # divs, so walking up from the h3 to "the nearest div" landed on
    # blog_title itself (title only, no date) rather than box_blog_top —
    # that was the bug that made this scraper return 0 results for months.
    # Selecting box_blog_top directly sidesteps the nesting entirely.
    gig_blocks = soup.select("div.box_blog_top")

    for box in gig_blocks:
        title_div = box.select_one("div.blog_title")
        h3 = title_div.find("h3") if title_div else None
        artist = h3.get_text(strip=True) if h3 else ""
        if not artist or len(artist) < 3:
            continue

        date_div = box.select_one("div.blog_date")
        date_text = date_div.get_text(separator=" ", strip=True) if date_div else ""

        # Format is "03 July2026" — day, space, month+year with no space
        # between month and year.
        date_m = re.search(
            r"(\d{1,2})\s*"
            r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
            r"June?|July?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
            r"Nov(?:ember)?|Dec(?:ember)?)"
            r"\s*(\d{4})",
            date_text, re.IGNORECASE
        )
        if not date_m:
            continue

        date_str = clean_date(
            f"{date_m.group(1)} {date_m.group(2)} {date_m.group(3)}"
        )
        if not is_future(date_str):
            continue

        # Full card wrapper. NOTE: each blog_content div nests the *next*
        # event's blog_content inside it (not as a sibling), so a plain
        # card.get_text() would bleed into the following event's price and
        # description text. Only take this card's own direct children, up
        # to (not including) the nested next blog_content div.
        card = box.find_parent("div", class_="blog_content") or box
        own_texts = []
        for child in card.find_all(recursive=False):
            if child.name == "div" and "blog_content" in (child.get("class") or []):
                break
            own_texts.append(child.get_text(separator=" ", strip=True))
        block_text = " ".join(own_texts)

        # Description — first paragraph after the h3 (find_next follows
        # document order, so it naturally lands on this card's own
        # paragraph before reaching the next nested event)
        desc_el = h3.find_next("p")
        description = desc_el.get_text(separator=" ", strip=True)[:400] if desc_el else ""

        # Ticket link — same document-order reasoning as description
        ticket_link = h3.find_next("a", href=re.compile(r"wegottickets|tickets"))
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
