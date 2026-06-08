"""
scraper_ukjazznews.py — UK Jazz News weekly newsletter parser
Source: https://ukjazznews.com/newsletter-continued/
Published every Wednesday. URL pattern: /newsletter-continued/DD-month-YYYY/
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

BASE_URL   = "https://ukjazznews.com"
NEWSLETTER = f"{BASE_URL}/newsletter-continued"

# Known London venues for filtering (lowercase)
LONDON_VENUES = {
    "vortex": ("Vortex Jazz Club", "North", "Dalston"),
    "606": ("606 Club", "South West", "Chelsea / Lots Road"),
    "ronnie": ("Ronnie Scott's", "Central", "Soho"),
    "pizza express": ("PizzaExpress Jazz Club", "Central", "Soho"),
    "karamel": ("Karamel", "North", "Wood Green"),
    "barbican": ("Barbican Centre", "Central", "Barbican / City"),
    "southbank": ("Southbank Centre", "Central", "Barbican / City"),
    "south bank": ("Southbank Centre", "Central", "Barbican / City"),
    "cadogan": ("Cadogan Hall", "Central", "Whitehall / Westminster"),
    "wigmore": ("Wigmore Hall", "Central", "Piccadilly"),
    "royal albert": ("Royal Albert Hall", "Central", "Piccadilly"),
    "lauderdale": ("Lauderdale House", "North", "Highgate / Archway"),
    "world heart beat": ("World Heart Beat", "South West", "Nine Elms / Battersea"),
    "jazz café posk": ("Jazz Café POSK", "West", "Hammersmith"),
    "posk": ("Jazz Café POSK", "West", "Hammersmith"),
    "east side jazz": ("East Side Jazz Club", "East", "Leytonstone"),
    "leytonstone": ("East Side Jazz Club", "East", "Leytonstone"),
    "highams park": ("Highams Park Jazz Club", "East", "Highams Park"),
    "bull's head": ("Bull's Head", "West / South West", "Barnes"),
    "bulls head": ("Bull's Head", "West / South West", "Barnes"),
    "crazy coqs": ("Crazy Coqs / Brasserie Zedel", "Central", "Piccadilly"),
    "brasserie zedel": ("Crazy Coqs / Brasserie Zedel", "Central", "Piccadilly"),
    "green note": ("Green Note", "North", "Camden"),
    "toulouse": ("Toulouse Lautrec", "South East", "Brixton"),
    "café oto": ("Café OTO", "North", "Dalston"),
    "cafe oto": ("Café OTO", "North", "Dalston"),
    "grow hackney": ("Grow Hackney", "East", "Hackney Wick"),
    "grow, hackney": ("Grow Hackney", "East", "Hackney Wick"),
    "oliver's jazz": ("Oliver's Jazz Bar", "South East", "Greenwich"),
    "spice of life": ("Spice of Life", "Central", "Soho"),
    "king's place": ("King's Place", "Central", "Barbican / City"),
    "kings place": ("King's Place", "Central", "Barbican / City"),
    "hampstead jazz": ("Hampstead Jazz Club", "North", "Hampstead"),
    "washington pub": ("The Washington", "North", "Hampstead"),
    "england's lane": ("The Washington", "North", "Hampstead"),
    "nw3": ("Various North London", "North", "Hampstead"),
    "haggerston": ("The Haggerston", "North", "Dalston"),
    "bull & gate": ("Bull & Gate", "North", "Kentish Town"),
    "cockpit": ("The Cockpit", "North", "Camden"),
    "map studio": ("Map Studio Café", "North", "Kentish Town"),
    "syp": ("SYP City", "North", "Islington / Angel"),
    "distillers": ("The Distillers", "West", "Hammersmith"),
    "george iv": ("George IV", "West", "Chiswick"),
    "drayton court": ("Drayton Court Hotel", "West", "Ealing"),
    "ladbroke hall": ("Ladbroke Hall", "West", "Notting Hill / Ladbroke Grove"),
    "mamasaint": ("MaMaSaint", "South West", "Tooting"),
    "oval tavern": ("Oval Tavern", "South West", "Croydon"),
    "croydon clock tower": ("Croydon Clock Tower Café", "South West", "Croydon"),
    "imber court": ("Imber Court", "West / South West", "East Molesey"),
    "twickenham": ("Twickenham Venue", "West / South West", "Twickenham"),
    "battersea barge": ("Battersea Barge", "South West", "Nine Elms / Battersea"),
    "piano smithfield": ("Piano Smithfield", "Central", "Barbican / City"),
    "flower station": ("The Garden Café / Flower Station", "North", "Highgate / Archway"),
}

# Outside M25 — exclude these
OUTSIDE_M25 = [
    "worthing", "chichester", "guildford", "dorking", "betchworth",
    "rochester", "edinburgh", "manchester", "cardiff", "poole",
    "broadstairs", "faversham", "whitstable", "eastbourne",
    "haverhill", "lincoln", "market harborough", "cambridge arts",
    "burrough on the hill", "brentwood essex", "southend",
    "upwell", "swaffham", "cheltenham",
]


def _get_current_newsletter_url() -> str:
    """Build URL for the most recent Wednesday newsletter."""
    today = datetime.now()
    # Find most recent Wednesday
    days_back = (today.weekday() - 2) % 7  # Wednesday = 2
    last_wed = today - timedelta(days=days_back)
    month_name = last_wed.strftime("%B").lower()
    return f"{NEWSLETTER}/{last_wed.day}-{month_name}-{last_wed.year}/"


def scrape() -> list:
    print("Scraping UK Jazz News...")
    results = []

    # Try current and previous two weeks
    today = datetime.now()
    for weeks_back in range(3):
        days_back = (today.weekday() - 2) % 7 + (weeks_back * 7)
        wed = today - timedelta(days=days_back)
        month_name = wed.strftime("%B").lower()
        url = f"{NEWSLETTER}/{wed.day}-{month_name}-{wed.year}/"

        print(f"  Trying: {url}")
        soup = fetch(url)
        if not soup:
            continue

        page_results = _parse_newsletter(soup, url)
        if page_results:
            results.extend(page_results)
            print(f"  Parsed {len(page_results)} gigs from {url}")
            break  # Found current newsletter, stop

    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r["gig_id"] not in seen:
            unique.append(r)
            seen.add(r["gig_id"])

    print(f"  Total UK Jazz News: {len(unique)} London gigs")
    return unique


def _parse_newsletter(soup, source_url: str) -> list:
    """Parse the Days and Weeks Ahead section of the newsletter."""
    results = []
    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Find the "Days and Weeks Ahead" section
    start_idx = 0
    for i, line in enumerate(lines):
        if "days and weeks ahead" in line.lower() or "live gigs" in line.lower():
            start_idx = i
            break

    # Find end section (Residencies or Radio)
    end_idx = len(lines)
    for i in range(start_idx, len(lines)):
        if any(s in lines[i].lower() for s in ["residencies", "radio", "courses", "not timed"]):
            end_idx = i
            break

    gig_lines = lines[start_idx:end_idx]

    current_date = None
    for line in gig_lines:
        # Check if line is a date indicator
        date_result = _extract_date(line)
        if date_result:
            current_date = date_result
            continue

        # Skip short lines, headers, navigation
        if len(line) < 10 or _is_boilerplate(line):
            continue

        # Skip if no current date context
        if not current_date:
            continue

        # Skip future dates too far away (> 3 months)
        if not is_future(current_date):
            continue

        # Check if line mentions a London venue
        venue_info = _identify_venue(line)
        if not venue_info:
            continue

        venue_name, zone, hood = venue_info

        # Parse the gig line
        result = _parse_gig_line(line, current_date, venue_name, zone, hood, source_url)
        if result:
            results.append(result)

    return results


def _extract_date(line: str) -> str | None:
    """Extract a date from a line like 'Thursday 4 June' or 'Monday 8 June'."""
    patterns = [
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
        r"(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"(?:\s+(\d{4}))?",
        r"(\d{1,2})\s+"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"(?:\s+(\d{4}))?",
    ]
    for pattern in patterns:
        m = re.search(pattern, line, re.IGNORECASE)
        if m:
            groups = m.groups()
            if len(groups) >= 2:
                day = groups[0] or groups[-3]
                month = groups[1] or groups[-2]
                year = groups[-1] or "2026"
                try:
                    return clean_date(f"{day} {month} {year}")
                except Exception:
                    continue
    return None


def _identify_venue(line: str) -> tuple | None:
    """Check if a line mentions a known London venue."""
    line_lower = line.lower()

    # Check outside M25 first
    for outside in OUTSIDE_M25:
        if outside in line_lower:
            return None

    # Check known London venues
    for keyword, venue_info in LONDON_VENUES.items():
        if keyword in line_lower:
            return venue_info

    # Check for London postcodes as a catch-all
    postcode_m = re.search(
        r"\b(N\d|NW\d|E\d|EC\d|SE\d|SW\d|W\d|WC\d)\b",
        line
    )
    if postcode_m:
        pc = postcode_m.group(1)
        zone, hood = _postcode_to_zone(pc)
        return (f"London Venue ({pc})", zone, hood)

    return None


def _postcode_to_zone(pc: str) -> tuple:
    """Rough zone assignment from postcode prefix."""
    mapping = {
        "N": ("North", "North London"), "NW": ("North", "North London"),
        "E": ("East", "East London"), "EC": ("Central", "Barbican / City"),
        "SE": ("South East", "South East London"),
        "SW": ("South West", "South West London"),
        "W": ("West", "West London"), "WC": ("Central", "Covent Garden"),
    }
    for prefix in ["NW","SW","SE","EC","WC","N","E","W"]:
        if pc.startswith(prefix):
            return mapping.get(prefix, ("Central", "London"))
    return ("Central", "London")


def _parse_gig_line(line: str, date: str, venue_name: str,
                    zone: str, hood: str, source_url: str) -> dict | None:
    """Extract artist and details from a newsletter gig line."""

    # Typical format:
    # "Thursday 4 June – Henry Lowther's Still Waters are at Karamel, 4 Coburg Road..."
    # "Friday 5th June – FIVE-WAY SPLIT FEAT. QUENTIN COLLINS are at Jazz Café POSK..."

    # Extract artist name — text before "are at", "is at", "at the", "at "
    artist = ""
    patterns = [
        r"^.*?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
        r"\s+\d+\w*\s+\w+\s*[–-]\s*(.+?)\s+(?:are|is)\s+at\b",
        r"[–-]\s+(.+?)\s+(?:are|is)\s+at\b",
        r"[–-]\s+(.+?)\s+at\s+(?:the\s+)?(?:" +
        "|".join(re.escape(k) for k in list(LONDON_VENUES.keys())[:20]) + ")",
    ]
    for pattern in patterns:
        m = re.search(pattern, line, re.IGNORECASE)
        if m:
            artist = m.group(1).strip()
            break

    # Fallback: everything before the venue mention
    if not artist:
        for keyword in LONDON_VENUES:
            idx = line.lower().find(keyword)
            if idx > 0:
                before = line[:idx].strip()
                # Clean up date prefix
                before = re.sub(
                    r"^.*?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
                    r"\s+\d+\w*\s+\w+\s*[–-]\s*",
                    "", before, flags=re.IGNORECASE
                ).strip()
                before = re.sub(r"\s+(?:are|is|–|-)\s*$", "", before).strip()
                if before and len(before) > 2:
                    artist = before
                    break

    if not artist or len(artist) < 3:
        return None

    # Clean artist name
    artist = re.sub(r"\s+(?:are|is)\s*$", "", artist).strip()
    artist = artist.rstrip("–-").strip()

    # Time if mentioned
    time_m = re.search(r"(\d{1,2})\s*(?:noon|pm|am)", line, re.IGNORECASE)
    start_time = time_m.group(0) if time_m else ""

    # Special occasion
    special = ""
    if "album launch" in line.lower():
        special = "Album launch"
    elif "birthday" in line.lower():
        special = "Birthday celebration"
    elif "farewell" in line.lower():
        special = "Farewell"

    return gig(
        artist_name=artist,
        venue_name=venue_name,
        date=date,
        start_time=start_time,
        source_url=source_url,
        ticket_url="",  # enricher will find this
        zone=zone,
        neighbourhood=hood,
        format_tags="Jazz Club",
        genre_tier1="Contemporary Jazz",
        special_occasion=special,
        venue_tier="1",
    )


def _is_boilerplate(line: str) -> bool:
    """Filter navigation and boilerplate text."""
    skip = [
        "read more", "book now", "find out more", "newsletter",
        "subscribe", "contact", "privacy", "cookie", "advertisement",
        "uk jazz news", "©", "powered by", "sign up",
    ]
    line_lower = line.lower()
    return any(s in line_lower for s in skip)


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new gigs from UK Jazz News")


if __name__ == "__main__":
    run()
