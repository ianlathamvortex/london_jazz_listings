"""
scraper_jazzcafe.py — The Jazz Café, Camden
https://thejazzcafelondon.com/whats-on/

The Jazz Café books jazz, soul, funk, hip-hop and Latin — broad programme.
We filter for jazz-relevant acts only using keyword + artist signals.
Ticketmaster is the primary ticket source and has a server-rendered venue page.
"""
import re, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup
from utils import gig, load, save, merge_gigs, clean_date, is_future

VENUE      = "Jazz Café Camden"
ZONE       = "North"
HOOD       = "Camden"
TUBE       = "Camden Town"
TIER       = "2"  # tier 2 — mixed programme, not purely jazz
BASE_URL   = "https://thejazzcafelondon.com"
EVENTS_URL = f"{BASE_URL}/whats-on/"
TM_URL     = "https://www.ticketmaster.co.uk/jazz-cafe-tickets-london/venue/255319"
SOURCE_URL = EVENTS_URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-GB,en;q=0.9",
}

# Acts/keywords that qualify as jazz-relevant for the Jazz Café programme
JAZZ_SIGNALS = [
    "jazz", "soul", "funk", "latin", "afro", "afrobeat", "bossa",
    "blues", "swing", "bebop", "fusion", "samba", "cumbia",
    "nubiyan", "soothsayers", "kyoto jazz", "jazz jamaica",
    "cookin on 3", "cookin\' on 3", "rhythm section",
]

# DJ nights, after-parties and clearly non-jazz bookings to skip
SKIP_SIGNALS = [
    "dj set", "after-party", "afterparty", "house music", "drum & bass",
    "dnb", "rave", "techno", "grime", "drill", "garage", "rnb night",
]


def _is_jazz_relevant(title: str) -> bool:
    t = title.lower()
    if any(s in t for s in SKIP_SIGNALS):
        return False
    return any(s in t for s in JAZZ_SIGNALS)


def _fetch(url: str) -> BeautifulSoup | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            return BeautifulSoup(r.read(), "html.parser")
    except Exception as e:
        print(f"  Fetch failed {url}: {e}")
        return None


def _parse_date(text: str) -> str | None:
    import datetime
    m = re.search(
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
        text
    )
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m2 = re.search(
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)(?:\s+(\d{4}))?",
        text, re.I
    )
    if m2:
        MONTHS = {
            "jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
            "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12",
        }
        day = m2.group(1).zfill(2)
        mon = MONTHS.get(m2.group(2).lower()[:3], "")
        year = m2.group(3) or str(datetime.date.today().year)
        if mon:
            return f"{year}-{mon}-{day}"
    return None


def scrape() -> list:
    print("Scraping Jazz Café Camden...")
    results = []
    seen = set()

    # Try the venue's own site first
    soup = _fetch(EVENTS_URL)
    if soup:
        for card in soup.find_all(["article", "div", "li"],
                                   class_=re.compile(r"event|show|listing|card", re.I)):
            h = card.find(["h1","h2","h3","h4"])
            if not h:
                continue
            title = h.get_text(strip=True)
            if not title or not _is_jazz_relevant(title):
                continue
            text = card.get_text(separator=" ", strip=True)
            date_str = _parse_date(text)
            if not date_str or not is_future(date_str):
                continue
            link = card.find("a", href=True)
            href = link["href"] if link else EVENTS_URL
            ticket_url = BASE_URL + href if href.startswith("/") else href
            key = f"{title.lower()}-{date_str}"
            if key in seen:
                continue
            seen.add(key)
            time_m = re.search(r"(\d{1,2}(?::\d{2})?)\s*(pm|am)", text, re.I)
            results.append(gig(
                artist_name=title, venue_name=VENUE, date=date_str,
                start_time=f"{time_m.group(1)}{time_m.group(2).lower()}" if time_m else "",
                ticket_url=ticket_url, source_url=SOURCE_URL,
                zone=ZONE, neighbourhood=HOOD, nearest_tube=TUBE,
                venue_tier=TIER, format_tags="Standing / Gig",
                genre_tier1="Contemporary Jazz",
            ))

    # Fallback: Ticketmaster venue page (server-rendered, reliable)
    if not results:
        soup2 = _fetch(TM_URL)
        if soup2:
            for item in soup2.find_all(["li", "div", "article"],
                                        class_=re.compile(r"event|listing|result", re.I)):
                h = item.find(["h1","h2","h3","h4","span"],
                               class_=re.compile(r"title|name|heading", re.I))
                title = h.get_text(strip=True) if h else item.get_text(strip=True)[:60]
                if not title or not _is_jazz_relevant(title):
                    continue
                text = item.get_text(separator=" ", strip=True)
                date_str = _parse_date(text)
                if not date_str or not is_future(date_str):
                    continue
                link = item.find("a", href=re.compile(r"ticketmaster"))
                ticket_url = link["href"] if link else TM_URL
                key = f"{title.lower()}-{date_str}"
                if key in seen:
                    continue
                seen.add(key)
                results.append(gig(
                    artist_name=title, venue_name=VENUE, date=date_str,
                    ticket_url=ticket_url, source_url=TM_URL,
                    zone=ZONE, neighbourhood=HOOD, nearest_tube=TUBE,
                    venue_tier=TIER, format_tags="Standing / Gig",
                    genre_tier1="Contemporary Jazz",
                ))

    print(f"  Found {len(results)} jazz-relevant Jazz Café Camden gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No Jazz Café Camden gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Jazz Café Camden gigs")


if __name__ == "__main__":
    run()
