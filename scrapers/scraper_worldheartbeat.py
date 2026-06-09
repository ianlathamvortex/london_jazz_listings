"""
scraper_worldheartbeat.py — World Heart Beat, Embassy Gardens, Nine Elms
Source: https://worldheartbeat.org/whats-on/
Mixed programme — filters by jazz categories from WordPress taxonomy.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "World Heart Beat"
ZONE     = "South West"
HOOD     = "Nine Elms / Battersea"
BASE_URL = "https://worldheartbeat.org"
EVENTS   = f"{BASE_URL}/whats-on/"

# Categories that indicate jazz content
JAZZ_CATS = {
    "jazz", "contemporary jazz", "blues / jazz", "jazz/global/rock",
    "jazz in the gardens 2026",
}

# Categories that indicate NOT jazz — skip even if jazz appears elsewhere
NON_JAZZ_CATS = {
    "rock / classical", "classical", "neo-classical", "folk", "folk-rock",
    "contemporary", "brazilian",  # Marcelo Bratke is classical piano
}

# Explicit non-jazz titles to skip
SKIP_TITLES = [
    "gig band special",
    "marcelo bratke",
    "olcay bayir",
    "jean-michel blais",
    "the khio trio",
    "the 286",
]


def _is_jazz_event(title: str, categories: list) -> bool:
    """Return True if event should be included."""
    title_lower = title.lower()
    cats_lower = {c.lower() for c in categories}

    # Skip explicit non-jazz titles
    if any(s in title_lower for s in SKIP_TITLES):
        return False

    # Skip if only non-jazz categories
    if cats_lower and cats_lower.issubset(NON_JAZZ_CATS):
        return False

    # Include if has jazz category
    if cats_lower & JAZZ_CATS:
        return True

    return False


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    soup = fetch(EVENTS)
    if not soup:
        return []

    results = []

    # Each event card has: image link, date, category tags, h3 title, book/info links
    # Find all event articles/cards
    event_blocks = (
        soup.select("article") or
        soup.select("div.event-card") or
        soup.select("div[class*='event']") or
        []
    )

    if not event_blocks:
        # Fallback: find h3 headings with surrounding context
        results = _parse_listing(soup)
    else:
        for block in event_blocks:
            result = _parse_block(block)
            if result:
                results.append(result)

    print(f"  Found {len(results)} future World Heart Beat jazz gigs")
    return results


def _parse_listing(soup) -> list:
    """Parse the listing page directly."""
    results = []
    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Find event entries by looking for date patterns followed by category then title
    i = 0
    while i < len(lines):
        # Date line: "Fri 12 Jun 2026"
        date_m = re.match(
            r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
            lines[i], re.IGNORECASE
        )
        if date_m:
            date_str = clean_date(f"{date_m.group(2)} {date_m.group(3)} {date_m.group(4)}")
            if not is_future(date_str):
                i += 1
                continue

            # Collect next few lines for categories and title
            context_lines = lines[i:i+6]
            context = " ".join(context_lines).lower()

            # Categories are on lines between date and title
            cats = []
            title = ""
            for j in range(1, min(5, len(lines) - i)):
                line = lines[i + j]
                # Title is usually the longest meaningful line
                if len(line) > 10 and not re.match(
                    r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)|Book now|More info|Embassy", 
                    line, re.I
                ):
                    if not title:
                        # Check if this looks like a category tag
                        if any(cat in line.lower() for cat in 
                               ["jazz", "rock", "classical", "folk", "blues", 
                                "reggae", "ska", "contemporary", "brazilian"]):
                            cats.append(line)
                        else:
                            title = line

            if not title:
                i += 1
                continue

            if not _is_jazz_event(title, cats):
                i += 1
                continue

            # Find ticket link
            ticket_url = EVENTS
            for j in range(i, min(i+8, len(lines))):
                if "ticketsolve" in lines[j].lower() or "gigantic" in lines[j].lower():
                    ticket_url = lines[j]
                    break

            # Genre from categories
            genre = "Contemporary Jazz"
            cats_str = " ".join(cats).lower()
            if "blues" in cats_str:
                genre = "Mainstream / Swing"
            elif "brazilian" in cats_str:
                genre = "Brazilian / MPB"

            # Special occasion
            special = ""
            title_lower = title.lower()
            if "birthday" in title_lower:
                special = "Birthday concert"
            elif "windrush" in title_lower:
                special = "Windrush Day celebration"

            results.append(gig(
                artist_name=title,
                venue_name=VENUE,
                date=date_str,
                ticket_url=ticket_url if ticket_url.startswith("http") else EVENTS,
                source_url=EVENTS,
                zone=ZONE,
                neighbourhood=HOOD,
                format_tags="Concert Hall",
                genre_tier1=genre,
                special_occasion=special,
                venue_tier="1",
            ))

        i += 1

    return results


def _parse_block(block) -> dict | None:
    """Parse a single event card block."""
    text = block.get_text(separator=" ", strip=True)

    # Title
    h = block.find(["h2", "h3", "h4"])
    title = h.get_text(strip=True) if h else ""
    if not title or len(title) < 3:
        return None

    # Categories from links
    cat_links = block.select("a[href*='event_category']")
    categories = [a.get_text(strip=True) for a in cat_links]

    if not _is_jazz_event(title, categories):
        return None

    # Date
    date_m = re.search(
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if not date_m:
        return None
    date_str = clean_date(f"{date_m.group(2)} {date_m.group(3)} {date_m.group(4)}")
    if not is_future(date_str):
        return None

    # Ticket link
    book_link = block.find("a", href=re.compile(r"ticketsolve|gigantic|book"))
    info_link  = block.find("a", href=re.compile(r"/whats-on/event/"))
    ticket_url = (book_link or info_link)
    ticket_url = ticket_url["href"] if ticket_url else EVENTS

    # Genre
    cats_str = " ".join(categories).lower()
    genre = "Contemporary Jazz"
    if "blues" in cats_str:
        genre = "Mainstream / Swing"
    elif "brazilian" in cats_str:
        genre = "Brazilian / MPB"

    special = ""
    if "birthday" in title.lower():
        special = "Birthday concert"
    elif "windrush" in title.lower():
        special = "Windrush Day celebration"

    return gig(
        artist_name=title,
        venue_name=VENUE,
        date=date_str,
        ticket_url=ticket_url if ticket_url.startswith("http") else BASE_URL + ticket_url,
        source_url=EVENTS,
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags="Concert Hall",
        genre_tier1=genre,
        special_occasion=special,
        venue_tier="1",
    )


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new World Heart Beat gigs")


if __name__ == "__main__":
    run()
