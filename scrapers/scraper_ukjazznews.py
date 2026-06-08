"""
scraper_ukjazznews.py — UK Jazz News weekly newsletter parser
Tries multiple approaches to get past 403 blocks.
"""
import re
import sys
import requests
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from bs4 import BeautifulSoup

BASE_URL   = "https://ukjazznews.com"
NEWSLETTER = f"{BASE_URL}/newsletter-continued"

HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.5",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)",
        "Accept": "text/html",
    },
]

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
    "oliver's jazz": ("Oliver's Jazz Bar", "South East", "Greenwich"),
    "spice of life": ("Spice of Life", "Central", "Soho"),
    "king's place": ("King's Place", "Central", "Barbican / City"),
    "kings place": ("King's Place", "Central", "Barbican / City"),
    "hampstead jazz": ("Hampstead Jazz Club", "North", "Hampstead"),
    "washington pub": ("The Washington", "North", "Hampstead"),
    "england's lane": ("The Washington", "North", "Hampstead"),
    "haggerston": ("The Haggerston", "North", "Dalston"),
    "bull & gate": ("Bull & Gate", "North", "Kentish Town"),
    "cockpit": ("The Cockpit", "North", "Camden"),
    "map studio": ("Map Studio Café", "North", "Kentish Town"),
    "syp": ("SYP City", "North", "Islington / Angel"),
    "george iv": ("George IV", "West", "Chiswick"),
    "drayton court": ("Drayton Court Hotel", "West", "Ealing"),
    "ladbroke hall": ("Ladbroke Hall", "West", "Notting Hill / Ladbroke Grove"),
    "mamasaint": ("MaMaSaint", "South West", "Tooting"),
    "oval tavern": ("Oval Tavern", "South West", "Croydon"),
    "croydon clock tower": ("Croydon Clock Tower Café", "South West", "Croydon"),
    "battersea barge": ("Battersea Barge", "South West", "Nine Elms / Battersea"),
    "piano smithfield": ("Piano Smithfield", "Central", "Barbican / City"),
    "flower station": ("The Garden Café", "North", "Highgate / Archway"),
    "orleans": ("Orleans Bar", "North", "Finsbury Park"),
    "night owl": ("The Night Owl", "North", "Finsbury Park"),
    "nw3": ("Various North London", "North", "Hampstead"),
}

OUTSIDE_M25 = [
    "worthing", "chichester", "guildford", "dorking", "betchworth",
    "rochester", "edinburgh", "manchester", "cardiff", "poole",
    "broadstairs", "faversham", "whitstable", "eastbourne",
    "haverhill", "lincoln", "market harborough", "cambridge arts",
    "burrough on the hill", "brentwood essex", "southend",
    "upwell", "swaffham", "cheltenham",
]


def fetch_with_retry(url):
    """Try multiple user agents."""
    for headers in HEADERS_LIST:
        try:
            session = requests.Session()
            # First hit the homepage to get cookies
            session.get(BASE_URL, headers=headers, timeout=10)
            r = session.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "lxml")
            print(f"  Status {r.status_code}")
        except Exception as e:
            print(f"  Fetch error: {e}")
    return None


def scrape() -> list:
    print("Scraping UK Jazz News...")
    results = []

    today = datetime.now()
    for weeks_back in range(4):
        days_back = (today.weekday() - 2) % 7 + (weeks_back * 7)
        wed = today - timedelta(days=days_back)
        month_name = wed.strftime("%B").lower()
        url = f"{NEWSLETTER}/{wed.day}-{month_name}-{wed.year}/"

        print(f"  Trying: {url}")
        soup = fetch_with_retry(url)
        if not soup:
            continue

        page_results = _parse_newsletter(soup, url)
        if page_results:
            results.extend(page_results)
            print(f"  Parsed {len(page_results)} London gigs")
            break

    seen = set()
    unique = []
    for r in results:
        if r["gig_id"] not in seen:
            unique.append(r)
            seen.add(r["gig_id"])

    print(f"  Total UK Jazz News: {len(unique)} London gigs")
    return unique


def _parse_newsletter(soup, source_url):
    results = []
    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    start_idx = 0
    for i, line in enumerate(lines):
        if "days and weeks ahead" in line.lower() or "live gigs" in line.lower():
            start_idx = i
            break

    end_idx = len(lines)
    for i in range(start_idx, len(lines)):
        if any(s in lines[i].lower() for s in
               ["residencies", "radio", "courses", "not timed", "live streamed"]):
            end_idx = i
            break

    gig_lines = lines[start_idx:end_idx]
    current_date = None

    for line in gig_lines:
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


def _extract_date(line):
    patterns = [
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
        r"(\d{1,2})\w*\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
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
                    return clean_date(f"{groups[0]} {groups[1]} {groups[2] if len(groups) > 2 else '2026'}")
                except Exception:
                    continue
    return None


def _identify_venue(line):
    line_lower = line.lower()
    for outside in OUTSIDE_M25:
        if outside in line_lower:
            return None
    for keyword, venue_info in LONDON_VENUES.items():
        if keyword in line_lower:
            return venue_info
    postcode_m = re.search(r"\b(N\d|NW\d|E\d|EC\d|SE\d|SW\d|W\d|WC\d)\b", line)
    if postcode_m:
        pc = postcode_m.group(1)
        zone, hood = _postcode_to_zone(pc)
        return (f"London Venue ({pc})", zone, hood)
    return None


def _postcode_to_zone(pc):
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
    patterns = [
        r"[–-]\s+(.+?)\s+(?:are|is)\s+at\b",
        r"[–-]\s+(.+?)\s+at\s+(?:the\s+)?",
    ]
    for pattern in patterns:
        m = re.search(pattern, line, re.IGNORECASE)
        if m:
            artist = m.group(1).strip()
            break

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

    time_m = re.search(r"(\d{1,2})\s*(?:noon|pm|am)", line, re.IGNORECASE)
    special = ""
    if "album launch" in line.lower():
        special = "Album launch"
    elif "birthday" in line.lower():
        special = "Birthday celebration"

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


def _is_boilerplate(line):
    skip = ["read more", "book now", "find out more", "newsletter",
            "subscribe", "contact", "privacy", "cookie", "uk jazz news",
            "©", "powered by", "sign up"]
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
