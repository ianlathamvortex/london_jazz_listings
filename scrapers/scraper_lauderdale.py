"""
scraper_lauderdale.py — Lauderdale House, Highgate
Source: https://www.lauderdalehouse.org.uk/whats-on/jazz-house
         https://www.lauderdalehouse.org.uk/whats-on/open-air-summer-season
         https://www.lauderdalehouse.org.uk/whats-on/music
"This is, we believe, London's top gig" — London Jazz News
Clean Drupal HTML — very reliable to scrape.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "Lauderdale House"
ZONE     = "North"
HOOD     = "Highgate / Archway"
BASE_URL = "https://www.lauderdalehouse.org.uk"

# All jazz-relevant listing pages
PAGES = [
    f"{BASE_URL}/whats-on/jazz-house",
    f"{BASE_URL}/whats-on/open-air-summer-season",
]

JAZZ_KEYWORDS = [
    "jazz", "quintet", "quartet", "trio", "saxophone", "trumpet",
    "latin", "soul", "swing", "bebop", "improvisation", "blues",
    "big band", "hammond", "funk", "afrobeat", "bossa nova",
]

SKIP_KEYWORDS = [
    "klezmer", "classical", "folk concert", "choir", "choral",
    "opera", "poetry", "comedy", "yoga", "pilates", "art class",
    "children", "kids", "watercolour", "drawing class",
]


def _is_jazz(text: str) -> bool:
    t = text.lower()
    if any(s in t for s in SKIP_KEYWORDS):
        return False
    return any(k in t for k in JAZZ_KEYWORDS)


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    results = []
    seen_urls = set()

    for page_url in PAGES:
        soup = fetch(page_url)
        if not soup:
            continue

        # Each event is a teaser with an h2/h3 link and a date
        teasers = (
            soup.select("article") or
            soup.select("div.view-content > div") or
            soup.select("div[class*='teaser']") or
            []
        )

        # Also grab direct event links
        event_links = soup.select("a[href*='/whats-on/']")
        for link in event_links:
            href = link.get("href", "")
            if not href or href in seen_urls:
                continue
            # Skip listing pages, not event pages
            skip_paths = ["/whats-on/by-day", "/whats-on/music",
                         "/whats-on/jazz-house", "/whats-on/open-air",
                         "/whats-on/adult", "/whats-on/children",
                         "/whats-on/exhibitions", "/whats-on/free",
                         "/whats-on/special", "/whats-on/highgate-festival"]
            if any(href == p or href.startswith(p + "?") for p in skip_paths):
                continue
            if href.count("/") < 2:
                continue

            seen_urls.add(href)
            full_url = href if href.startswith("http") else BASE_URL + href
            result = _scrape_event(full_url)
            if result and is_future(result["date"]):
                results.append(result)

    # Deduplicate
    seen_ids = set()
    unique = []
    for r in results:
        if r["gig_id"] not in seen_ids:
            unique.append(r)
            seen_ids.add(r["gig_id"])

    print(f"  Found {len(unique)} future Lauderdale gigs")
    return unique


def _scrape_event(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    text = soup.get_text(separator=" ", strip=True)

    # Jazz filter
    if not _is_jazz(text):
        return None

    # Title — h1 with "Styled heading" prefix pattern
    h1 = soup.find("h1")
    if not h1:
        return None
    title = h1.get_text(strip=True)
    # Clean up "Jazz in the House ARQ" → "ARQ" or keep full title
    # Remove "Styled heading" prefix if present
    title = re.sub(r"^Styled heading\s*", "", title).strip()
    # Clean "Jazz in the House " prefix for artist name
    artist = re.sub(r"^Jazz (?:in the House|on the Tea Lawn)[:\s]*", "", title).strip()
    artist = re.sub(r"^Open-Air Thursdays:\s*", "", artist).strip()
    if not artist:
        artist = title

    # Date — Lauderdale uses "Thursday 11 June" or "Thursday 11 June 8:00pm"
    date_m = re.search(
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
        r"(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)"
        r"(?:\s+(\d{4}))?",
        text, re.IGNORECASE
    )
    if not date_m:
        return None
    year = date_m.group(3) or "2026"
    date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")

    # Time
    time_m = re.search(r"(\d{1,2}[:.]\d{2})\s*(pm|am)?", text, re.IGNORECASE)
    start_time = time_m.group(0) if time_m else "20:00"

    # Doors
    doors_m = re.search(r"[Dd]oors?\s+open\s+at\s+(\d{1,2}[:.]\d{2})", text)
    doors_time = doors_m.group(1) if doors_m else ""

    # Price
    price_m = re.search(r"Standard\s+£(\d+(?:\.\d{2})?)", text)
    if not price_m:
        price_m = re.search(r"£(\d+(?:\.\d{2})?)", text)
    price = f"£{price_m.group(1)}" if price_m else ""

    # Ticket link
    book_link = soup.find("a", href=re.compile(r"ticketsolve|tickets"))
    ticket_url = book_link["href"] if book_link else url

    # Description — first substantial paragraph after h1
    desc = ""
    for p in soup.find_all("p"):
        p_text = p.get_text(strip=True)
        if len(p_text) > 80 and not any(
            skip in p_text.lower() for skip in
            ["cookie", "privacy", "terms", "booking fee", "concession"]
        ):
            desc = p_text[:400]
            break

    # Format — outdoor or indoor
    is_outdoor = any(k in text.lower() for k in ["tea lawn", "outdoor", "open-air"])
    fmt = "Outdoor" if is_outdoor else "Jazz Club"

    # Genre
    genre = "Contemporary Jazz"
    if "latin" in text.lower():
        genre = "Latin"
    elif "soul" in text.lower() or "house" in text.lower():
        genre = "Soul & Groove"

    # Special occasion
    special = ""
    if "anniversary" in text.lower():
        special = "Anniversary"
    elif "album" in text.lower():
        special = "Album feature"

    return gig(
        artist_name=artist,
        venue_name=VENUE,
        date=date_str,
        start_time=start_time,
        doors_time=doors_time,
        price_from=price,
        ticket_url=ticket_url,
        source_url=url,
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags=fmt,
        genre_tier1=genre,
        description=desc,
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
    print(f"  Added {added} new Lauderdale House gigs")


if __name__ == "__main__":
    run()
