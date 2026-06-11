"""
scraper_lauderdale.py — Lauderdale House, Highgate
https://www.lauderdalehouse.org.uk/whats-on/music
Drupal CMS — server-rendered, no Playwright needed.
Scrapes the music page and Jazz in the House series.
Filters for jazz events only.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import urllib.request
from bs4 import BeautifulSoup
from utils import gig, load, save, merge_gigs, clean_date, is_future, is_jazz_event

VENUE   = "Lauderdale House"
ZONE    = "North"
HOOD    = "Highgate"
TUBE    = "Highgate / Archway"
TIER    = "1"
BASE    = "https://www.lauderdalehouse.org.uk"
PAGES   = [
    f"{BASE}/whats-on/music",
    f"{BASE}/whats-on/jazz-house",
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
}

JAZZ_SIGNALS = [
    "jazz", "arq", "alison rayner", "improvisation", "blues",
    "swing", "bebop", "quartet", "quintet", "trio", "sax",
]

MONTHS = {
    "january":"01","february":"02","march":"03","april":"04",
    "may":"05","june":"06","july":"07","august":"08",
    "september":"09","october":"10","november":"11","december":"12",
    "jan":"01","feb":"02","mar":"03","apr":"04","jun":"06",
    "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12",
}


def _parse_date(text: str) -> str | None:
    """Parse 'Thursday 11 June' or '11 June 2026' → '2026-06-11'"""
    import datetime
    m = re.search(
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)(?:\s+(\d{4}))?",
        text, re.I
    )
    if not m:
        return None
    day = int(m.group(1))
    mon_key = m.group(2).lower()[:3]
    mon = MONTHS.get(mon_key)
    if not mon:
        return None
    year = m.group(3) or str(datetime.date.today().year)
    # If month is earlier than current month and no year given, assume next year
    if not m.group(3):
        today = datetime.date.today()
        candidate = f"{year}-{mon}-{day:02d}"
        if candidate < today.isoformat():
            year = str(int(year) + 1)
    return f"{year}-{mon}-{day:02d}"


def _is_jazz(title: str, desc: str) -> bool:
    combined = (title + " " + desc).lower()
    return any(s in combined for s in JAZZ_SIGNALS)


def _fetch(url: str) -> BeautifulSoup | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return BeautifulSoup(r.read(), "html.parser")
    except Exception as e:
        print(f"  Failed to fetch {url}: {e}")
        return None


def scrape() -> list:
    print("Scraping Lauderdale House...")
    results = []
    seen_ids = set()

    for page_url in PAGES:
        soup = _fetch(page_url)
        if not soup:
            continue

        # Each event is in a div/article with a heading and a date
        # Drupal renders them as teaser nodes
        for heading in soup.find_all(["h2", "h3"]):
            title = heading.get_text(strip=True)
            if not title or len(title) < 4:
                continue

            # Walk up to find the event container
            container = heading.find_parent(["article", "div", "li", "section"])
            if not container:
                continue

            text = container.get_text(separator=" ", strip=True)
            desc = ""
            # Find description paragraph
            for p in container.find_all("p"):
                p_text = p.get_text(strip=True)
                if len(p_text) > 30 and p_text != title:
                    desc = p_text[:200]
                    break

            if not _is_jazz(title, desc):
                continue

            date_str = _parse_date(text)
            if not date_str or not is_future(date_str):
                continue

            # Ticket/event link
            link = heading.find("a") or container.find("a", href=re.compile(r"/whats-on/"))
            if link and link.get("href", "").startswith("/"):
                event_url = BASE + link["href"]
            elif link:
                event_url = link.get("href", page_url)
            else:
                event_url = page_url

            # Strip "Jazz in the House: " prefix from title for artist_name
            artist = re.sub(r"^Jazz in the House:\s*", "", title, flags=re.I).strip()
            artist = re.sub(r"^Jazz:\s*", "", artist, flags=re.I).strip()

            g = gig(
                artist_name=artist, venue_name=VENUE, date=date_str,
                ticket_url=event_url, source_url=page_url,
                zone=ZONE, neighbourhood=HOOD,
                venue_tier=TIER, format_tags="Concert Hall",
                genre_tier1="Contemporary Jazz",
                description=desc[:120] if desc else "",
            )
            gig_id = g["gig_id"]
            if gig_id not in seen_ids:
                results.append(g)
                seen_ids.add(gig_id)

    print(f"  Found {len(results)} future Lauderdale jazz events")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No Lauderdale gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Lauderdale House gigs")


if __name__ == "__main__":
    run()
