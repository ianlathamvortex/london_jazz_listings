"""
scraper_ronnies.py — Ronnie Scott's Jazz Club
https://www.ronniescotts.co.uk/find-a-show

The site is server-rendered and paginated (?page=N, 19 pages).
No Playwright needed. Scrapes all pages and filters out:
- Late Late Shows (weekly residencies → jam_sessions.json)
- Vocal Jazz Jam (→ jam_sessions.json)
- Clearly non-jazz bookings (DJ nights, comedy, classical)

Show types on site:
  Main Show, Upstairs at Ronnie's, Sunday Lunch, Lunch Show,
  Late Late Show, Late Late Show Upstairs, External Show
"""
import re, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup
from utils import gig, load, save, merge_gigs, clean_date, is_future

VENUE    = "Ronnie Scott's"
ZONE     = "Central"
HOOD     = "Soho"
TUBE     = "Leicester Square / Tottenham Court Road"
TIER     = "1"
BASE_URL = "https://www.ronniescotts.co.uk"
LIST_URL = f"{BASE_URL}/find-a-show"
CAL_URL  = f"{BASE_URL}/show-calendar"  # calendar view has all shows by date

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-GB,en;q=0.9",
}

# These show types are weekly residencies — skip them (in jam_sessions.json)
SKIP_SHOW_TYPES = {
    "Late Late Show",
    "Late Late Show Upstairs",
}

# These title fragments are recurring residencies to skip
SKIP_TITLE_FRAGMENTS = [
    "late late show",
    "vocal jazz jam",
    "ronnie scott's jazz jam",
    "jazz jam",
]

# Editors pick signals
EDITORS_PICK_SIGNALS = [
    "grammy", "mercury prize", "international", "miles davis",
    "john coltrane", "herbie hancock", "wayne shorter",
]

MONTHS = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
}


def _parse_date(text: str) -> str | None:
    """Parse 'Thu 18 Jun 2026' or 'Fri 19 - Sun 21 Jun 2026' → first date"""
    import datetime
    # Handle date ranges — take the first date
    text = text.strip()
    m = re.search(
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:\s+(\d{4}))?",
        text, re.I
    )
    if not m:
        return None
    day = int(m.group(1))
    mon = MONTHS.get(m.group(2).lower()[:3], 0)
    year = int(m.group(3)) if m.group(3) else datetime.date.today().year
    if not mon:
        return None
    return f"{year}-{mon:02d}-{day:02d}"


def _stage_to_format(show_type: str) -> tuple:
    """Return (stage, format_tags, start_time)"""
    if "Upstairs" in show_type:
        return "Upstairs at Ronnie's", "Jazz Club", "19:30"
    if "Sunday Lunch" in show_type or "Lunch" in show_type:
        return "Main Stage", "Jazz Club", "12:00"
    if "Main Show" in show_type:
        return "Main Stage", "Jazz Club", "20:00"
    return "Main Stage", "Jazz Club", "20:00"


def _fetch_page(page: int, url: str = "") -> BeautifulSoup | None:
    url = url or (LIST_URL if page == 1 else f"{LIST_URL}?page={page}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return BeautifulSoup(r.read(), "html.parser")
    except Exception as e:
        print(f"  Page {page} failed: {e}")
        return None


def _count_pages(soup: BeautifulSoup) -> int:
    """Find highest page number from pagination links"""
    pages = []
    for a in soup.find_all("a", href=re.compile(r"find-a-show\?page=")):
        m = re.search(r"page=(\d+)", a["href"])
        if m:
            pages.append(int(m.group(1)))
    return max(pages) if pages else 1


def scrape() -> list:
    print("Scraping Ronnie Scott's (paginated server-rendered)...")
    results = []
    seen_ids = set()

    # Get page 1 and find total pages
    soup1 = _fetch_page(1)
    if not soup1:
        print("  Failed to fetch page 1")
        return []

    total_pages = min(_count_pages(soup1), 8)  # cap at 8 pages (~3 months ahead)
    print(f"  {total_pages} pages to scrape")

    # Try show-calendar first — has all shows in date order, one page
    cal_soup = _fetch_page(1, url=f"{BASE_URL}/show-calendar")
    if cal_soup:
        soups = [cal_soup]
        print("  Using show-calendar view")
    else:
        soups = [soup1]
        for page in range(2, total_pages + 1):
            s = _fetch_page(page)
            if s:
                soups.append(s)

    for soup in soups:
        # Each show is a block containing: show type label, date, h2 title, description, link
        # They appear as adjacent elements — find h2s and walk up to the container
        for h2 in soup.find_all("h2"):
            title = h2.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            # Skip residencies
            title_lower = title.lower()
            if any(f in title_lower for f in SKIP_TITLE_FRAGMENTS):
                continue

            # Find show container — walk up to a div that has the show type label
            container = h2.find_parent("div") or h2.find_parent("article") or h2.find_parent("section")
            if not container:
                continue

            container_text = container.get_text(separator="\n", strip=True)

            # Show type
            show_type = ""
            for st in ["Main Show", "Upstairs at Ronnie's", "Sunday Lunch",
                       "Lunch Show", "Late Late Show Upstairs", "Late Late Show",
                       "External Show"]:
                if st in container_text:
                    show_type = st
                    break

            # Skip late late shows
            if show_type in SKIP_SHOW_TYPES:
                continue

            # Date
            date_m = re.search(
                r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+"
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:\s+(\d{4}))?",
                container_text, re.I
            )
            if not date_m:
                continue
            day = int(date_m.group(2))
            mon = MONTHS.get(date_m.group(3).lower()[:3], 0)
            import datetime
            year = int(date_m.group(4)) if date_m.group(4) else datetime.date.today().year
            if not mon:
                continue
            date_str = f"{year}-{mon:02d}-{day:02d}"
            if not is_future(date_str):
                continue

            # Skip date ranges that are recurring (same act on multiple dates = residency)
            # "Fri 19 Jun - Fri 11 Dec 2026" → recurring, skip
            range_m = re.search(
                r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}\s+\w+\s*[-–]\s*"
                r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}",
                container_text, re.I
            )
            if range_m and show_type not in ("Main Show", "Sunday Lunch"):
                continue  # recurring Upstairs residency — skip

            # Ticket URL from link
            link = h2.find("a") or container.find("a", href=re.compile(r"/find-a-show/"))
            if link and link.get("href", "").startswith("/find-a-show/"):
                ticket_url = BASE_URL + link["href"]
                slug = link["href"].split("/find-a-show/")[-1].strip("/")
            else:
                ticket_url = LIST_URL
                slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

            # Description
            desc_el = container.find("p")
            description = desc_el.get_text(strip=True)[:200] if desc_el else ""

            # Sold out?
            sold_out = "sold out" in container_text.lower()

            stage, format_tags, start_time = _stage_to_format(show_type)

            # Editors pick
            ep = any(s in (title + description).lower() for s in EDITORS_PICK_SIGNALS)

            # Build gig_id
            gig_id = re.sub(r"[^a-z0-9]+", "-",
                            f"{title}-ronnies-{date_str}".lower()).strip("-")[:80]
            if gig_id in seen_ids:
                continue
            seen_ids.add(gig_id)

            g = gig(
                artist_name=title,
                venue_name=VENUE,
                date=date_str,
                start_time=start_time,
                ticket_url=ticket_url,
                source_url=LIST_URL,
                stage=stage,
                zone=ZONE,
                neighbourhood=HOOD,
                nearest_tube=TUBE,
                venue_tier=TIER,
                format_tags=format_tags,
                genre_tier1="Contemporary Jazz",
                description=description,
            )
            g["gig_id"] = gig_id
            g["editors_pick"] = ep
            g["description_verified"] = False
            g["description_source"] = "ronniescotts.co.uk"

            results.append(g)

    print(f"  Found {len(results)} future Ronnie's shows")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No Ronnie's gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Ronnie's gigs")


if __name__ == "__main__":
    run()
