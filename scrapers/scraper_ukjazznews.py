"""
scraper_ukjazznews.py — UK Jazz News weekly newsletter
Uses Playwright to bypass Cloudflare bot protection.
The newsletter listings page is publicly accessible — just needs a real browser.
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from browser import fetch_browser, PLAYWRIGHT_AVAILABLE

BASE_URL   = "https://ukjazznews.com"
NEWSLETTER = f"{BASE_URL}/newsletter-continued"

LONDON_VENUES = {
    "vortex": ("Vortex Jazz Club", "North", "Dalston"),
    "606": ("606 Club", "South West", "Chelsea / Lots Road"),
    "ronnie": ("Ronnie Scott's", "Central", "Soho"),
    "pizza express": ("PizzaExpress Jazz Club", "Central", "Soho"),
    "pheasantry": ("PizzaExpress The Pheasantry", "South West", "Chelsea / Lots Road"),
    "karamel": ("Karamel", "North", "Wood Green"),
    "barbican": ("Barbican Centre", "Central", "Barbican / City"),
    "southbank": ("Southbank Centre", "Central", "Barbican / City"),
    "south bank": ("Southbank Centre", "Central", "Barbican / City"),
    "cadogan": ("Cadogan Hall", "Central", "Whitehall / Westminster"),
    "wigmore": ("Wigmore Hall", "Central", "Piccadilly"),
    "royal albert": ("Royal Albert Hall", "Central", "Piccadilly"),
    "royal festival hall": ("Royal Festival Hall", "Central", "Barbican / City"),
    "queen elizabeth hall": ("Queen Elizabeth Hall", "Central", "Barbican / City"),
    "lauderdale": ("Lauderdale House", "North", "Highgate / Archway"),
    "world heart beat": ("World Heart Beat", "South West", "Nine Elms / Battersea"),
    "jazz café posk": ("Jazz Café POSK", "West", "Hammersmith"),
    "posk": ("Jazz Café POSK", "West", "Hammersmith"),
    "east side jazz": ("East Side Jazz Club", "East", "Leytonstone"),
    "highams park": ("Highams Park Jazz Club", "East", "Highams Park"),
    "bull's head": ("Bull's Head Barnes", "West / South West", "Barnes"),
    "bulls head": ("Bull's Head Barnes", "West / South West", "Barnes"),
    "crazy coqs": ("Crazy Coqs / Brasserie Zedel", "Central", "Piccadilly"),
    "brasserie zedel": ("Crazy Coqs / Brasserie Zedel", "Central", "Piccadilly"),
    "green note": ("Green Note", "North", "Camden"),
    "toulouse": ("Toulouse Lautrec", "South East", "Brixton"),
    "café oto": ("Café OTO", "North", "Dalston"),
    "cafe oto": ("Café OTO", "North", "Dalston"),
    "grow hackney": ("Grow Hackney", "East", "Hackney Wick"),
    "oliver's jazz": ("Oliver's Jazz Bar", "South East", "Greenwich"),
    "spice of life": ("Spice of Life", "Central", "Soho"),
    "king's place": ("King's Place", "Central", "Barbican / City"),
    "kings place": ("King's Place", "Central", "Barbican / City"),
    "hampstead jazz": ("Hampstead Jazz Club", "North", "Hampstead"),
    "haggerston": ("The Haggerston", "North", "Dalston"),
    "cockpit": ("The Cockpit", "North", "Camden"),
    "map studio": ("Map Studio Café", "North", "Kentish Town"),
    "ladbroke hall": ("Ladbroke Hall", "West", "Notting Hill / Ladbroke Grove"),
    "pollini": ("Pollini at Ladbroke Hall", "West", "Notting Hill / Ladbroke Grove"),
    "brunswick house": ("Brunswick House", "South West", "Nine Elms / Battersea"),
    "darby's": ("Darby's", "South West", "Nine Elms / Battersea"),
    "below stone nest": ("Below Stone Nest", "Central", "Soho"),
    "stone nest": ("Below Stone Nest", "Central", "Soho"),
    "one club row": ("One Club Row", "East", "Bethnal Green"),
    "night tales": ("Night Tales Loft", "East", "Hackney Wick"),
    "jazzlive": ("Jazzlive at The Crypt", "South East", "Camberwell"),
    "the crypt": ("Jazzlive at The Crypt", "South East", "Camberwell"),
    "orleans": ("Orleans Bar", "North", "Finsbury Park"),
    "george iv": ("George IV", "West", "Chiswick"),
    "drayton court": ("Drayton Court Hotel", "West", "Ealing"),
    "mamasaint": ("MaMaSaint", "South West", "Tooting"),
    "oval tavern": ("Oval Tavern", "South West", "Croydon"),
    "battersea barge": ("Battersea Barge", "South West", "Nine Elms / Battersea"),
    "piano smithfield": ("Piano Smithfield", "Central", "Barbican / City"),
    "syp": ("SYP City", "North", "Islington / Angel"),
    "jazz cafe": ("Jazz Café", "North", "Camden"),
    "koko": ("KOKO", "North", "Camden"),
    "union chapel": ("Union Chapel", "North", "Islington / Angel"),
    "earth hackney": ("EartH Theatre", "North", "Dalston"),
    "nw3": ("Various North London", "North", "Hampstead"),
}

OUTSIDE_M25 = [
    "worthing", "chichester", "guildford", "dorking", "betchworth",
    "rochester", "edinburgh", "manchester", "cardiff", "poole",
    "broadstairs", "faversham", "whitstable", "eastbourne",
    "haverhill", "lincoln", "market harborough", "cambridge arts",
    "burrough on the hill", "brentwood essex", "southend",
    "upwell", "swaffham", "cheltenham", "oxford", "bristol",
    "birmingham", "leeds", "liverpool", "glasgow", "brighton",
    "folkestone", "margate", "ramsgate", "deal", "sandwich",
]


def _get_newsletter_urls() -> list[str]:
    """Build URLs for the most recent 4 Wednesday newsletters."""
    urls = []
    today = datetime.now()
    for weeks_back in range(4):
        days_back = (today.weekday() - 2) % 7 + (weeks_back * 7)
        wed = today - timedelta(days=days_back)
        month_name = wed.strftime("%B").lower()
        urls.append(f"{NEWSLETTER}/{wed.day}-{month_name}-{wed.year}/")
    return urls


def scrape() -> list:
    print("Scraping UK Jazz News...")

    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available — skipping UK Jazz News")
        print("  Install with: pip install playwright && playwright install chromium")
        return []

    results = []

    for url in _get_newsletter_urls():
        print(f"  Trying: {url}")
        soup = fetch_browser(url, wait_for="article, .entry-content, .post-content")
        if not soup:
            continue

        # Check we got actual content
        text = soup.get_text(separator="\n", strip=True)
        if len(text) < 500:
            print(f"  Page too short ({len(text)} chars) — likely blocked")
            continue

        if "days and weeks ahead" not in text.lower() and "live gigs" not in text.lower():
            print(f"  No listings section found")
            continue

        page_results = _parse_newsletter(soup, url)
        if page_results:
            results.extend(page_results)
            print(f"  Parsed {len(page_results)} London gigs from {url}")
            break  # Found current newsletter

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
    results = []
    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Find "Days and Weeks Ahead" section
    start_idx = 0
    for i, line in enumerate(lines):
        if any(s in line.lower() for s in
               ["days and weeks ahead", "live gigs this week",
                "gigs this week", "days & weeks ahead"]):
            start_idx = i
            break

    if start_idx == 0:
        print("  Could not find 'Days and Weeks Ahead' section")
        return []

    # Find end of section
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        if any(s in lines[i].lower() for s in
               ["residencies", "radio listings", "courses",
                "not timed", "live streamed", "read elsewhere",
                "news features", "album reviews"]):
            end_idx = i
            break

    gig_lines = lines[start_idx:end_idx]
    print(f"  Found listings section: {len(gig_lines)} lines")

    current_date = None
    for line in gig_lines:
        # Date line
        date_result = _extract_date(line)
        if date_result:
            current_date = date_result
            continue

        if len(line) < 10 or _is_boilerplate(line):
            continue

        if not current_date or not is_future(current_date):
            continue

        venue_info = _identify_venue(line)
        if not venue_info:
            continue

        venue_name, zone, hood = venue_info
        result = _parse_gig_line(line, current_date, venue_name, zone, hood, source_url)
        if result:
            results.append(result)

    return results


def _extract_date(line: str) -> str | None:
    patterns = [
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
        r"(\d{1,2})\w*\s+"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)"
        r"(?:\s+(\d{4}))?",
        r"(\d{1,2})\s+"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"(?:\s+(\d{4}))?",
    ]
    for pattern in patterns:
        m = re.search(pattern, line, re.IGNORECASE)
        if m:
            groups = [g for g in m.groups() if g]
            if len(groups) >= 2:
                try:
                    year = groups[2] if len(groups) > 2 else "2026"
                    return clean_date(f"{groups[0]} {groups[1]} {year}")
                except Exception:
                    continue
    return None


def _identify_venue(line: str) -> tuple | None:
    line_lower = line.lower()
    for outside in OUTSIDE_M25:
        if outside in line_lower:
            return None
    for keyword, venue_info in LONDON_VENUES.items():
        if keyword in line_lower:
            return venue_info
    # Catch London postcodes
    postcode_m = re.search(r"\b(N\d|NW\d|E\d|EC\d|SE\d|SW\d|W\d|WC\d)\b", line)
    if postcode_m:
        pc = postcode_m.group(1)
        zone, hood = _postcode_to_zone(pc)
        return (f"London Venue ({pc})", zone, hood)
    return None


def _postcode_to_zone(pc: str) -> tuple:
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


def _parse_gig_line(line, date, venue_name, zone, hood, source_url):
    artist = ""

    # Pattern: "Thursday 11 June – John Smith Quartet are at Vortex"
    # or just: "John Smith Quartet are at Vortex, N16, 7.30pm"
    patterns = [
        r"[–\-]\s+(.+?)\s+(?:are|is)\s+at\b",
        r"[–\-]\s+(.+?)\s+at\s+(?:the\s+)?(?:" +
        "|".join(re.escape(k) for k in list(LONDON_VENUES.keys())[:30]) + ")",
    ]
    for pattern in patterns:
        m = re.search(pattern, line, re.IGNORECASE)
        if m:
            artist = m.group(1).strip()
            break

    # Fallback: text before venue keyword
    if not artist:
        for keyword in LONDON_VENUES:
            idx = line.lower().find(keyword)
            if idx > 5:
                before = line[:idx].strip()
                before = re.sub(
                    r"^.*?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
                    r"\s+\d+\w*\s+\w+\s*[–\-]\s*",
                    "", before, flags=re.IGNORECASE
                ).strip()
                before = re.sub(r"\s+(?:are|is|–|-)\s*$", "", before).strip()
                if before and len(before) > 2:
                    artist = before
                    break

    if not artist or len(artist) < 3:
        return None

    artist = re.sub(r"\s+(?:are|is)\s*$", "", artist).strip().rstrip("–-").strip()

    # Clean up leading date fragments
    artist = re.sub(
        r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
        r"\s+\d+\w*\s+\w+\s*[–\-]\s*",
        "", artist, flags=re.IGNORECASE
    ).strip()

    if not artist or len(artist) < 3:
        return None

    time_m = re.search(r"(\d{1,2}[.:]\d{2})\s*(?:pm|am)?", line, re.IGNORECASE)
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
        start_time=time_m.group(0) if time_m else "",
        source_url=source_url,
        ticket_url="",
        zone=zone,
        neighbourhood=hood,
        format_tags="Jazz Club",
        genre_tier1="Contemporary Jazz",
        special_occasion=special,
    )


def _is_boilerplate(line: str) -> bool:
    skip = [
        "read more", "book now", "find out more", "newsletter",
        "subscribe", "contact", "privacy", "cookie", "uk jazz news",
        "©", "powered by", "sign up", "advertisement", "advertise",
        "click here", "days and weeks ahead",
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
