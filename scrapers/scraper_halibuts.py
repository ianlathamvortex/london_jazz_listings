"""
scraper_halibuts.py — Halibuts.com jazz listings scraper
Scrapes halibuts.com/genre/jazz/{page} (server-side rendered, no Playwright needed).
Fetches pages 1–N until no events found. Only picks up venues already in our
known venue map; others are captured as raw data for manual review.
"""

import re
import json
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta
from bs4 import BeautifulSoup

# Map Halibuts venue names → our venue metadata
# Add more as needed; anything not in this map will be skipped
VENUE_MAP = {
    "606 Club":                 {"venue_name": "606 Jazz Club",     "zone": "South West",  "neighbourhood": "Chelsea",         "venue_tier": "1"},
    "Barbican Hall":            {"venue_name": "Barbican",          "zone": "Central",     "neighbourhood": "Barbican",        "venue_tier": "1"},
    "Barbican Centre":          {"venue_name": "Barbican",          "zone": "Central",     "neighbourhood": "Barbican",        "venue_tier": "1"},
    "Cadogan Hall":             {"venue_name": "Cadogan Hall",      "zone": "Central",     "neighbourhood": "Chelsea",         "venue_tier": "1"},
    "Cafè Oto":                 {"venue_name": "Café OTO",          "zone": "East",        "neighbourhood": "Dalston",         "venue_tier": "1"},
    "EartH":                    {"venue_name": "EartH Theatre",     "zone": "North",       "neighbourhood": "Hackney",         "venue_tier": "1"},
    "Grow":                     {"venue_name": "Grow",              "zone": "East",        "neighbourhood": "Hackney Wick",    "venue_tier": "1"},
    "Jazzlive at the Crypt":    {"venue_name": "Jazzlive at The Crypt","zone": "South East","neighbourhood": "Greenwich",       "venue_tier": "1"},
    "Karamel N22":              {"venue_name": "Karamel",           "zone": "North",       "neighbourhood": "Wood Green",      "venue_tier": "2"},
    "Kings Place":              {"venue_name": "King's Place",      "zone": "Central",     "neighbourhood": "King's Cross",    "venue_tier": "1"},
    "Lauderdale House":         {"venue_name": "Lauderdale House",  "zone": "North",       "neighbourhood": "Highgate",        "venue_tier": "1"},
    "Pizza Express Jazz Club":  {"venue_name": "PizzaExpress Jazz Club","zone": "Central", "neighbourhood": "Soho",            "venue_tier": "2"},
    "Ronnie Scott's Jazz Club": {"venue_name": "Ronnie Scott's",    "zone": "Central",     "neighbourhood": "Soho",            "venue_tier": "1"},
    "Royal Albert Hall":        {"venue_name": "Royal Albert Hall", "zone": "West",        "neighbourhood": "South Kensington","venue_tier": "1"},
    "Toulouse Lautrec Jazz Club":{"venue_name":"Toulouse Lautrec",  "zone": "South",       "neighbourhood": "Kennington",      "venue_tier": "1"},
    "Vortex Jazz Club":         {"venue_name": "Vortex Jazz Club",  "zone": "North",       "neighbourhood": "Dalston",         "venue_tier": "1"},
    "Wigmore Hall":             {"venue_name": "Wigmore Hall",      "zone": "Central",     "neighbourhood": "Marylebone",      "venue_tier": "1"},
    "World Heart Beat Embassy Gardens": {"venue_name":"World Heart Beat","zone":"South West","neighbourhood":"Nine Elms",      "venue_tier": "1"},
    "Blackheath Halls":         {"venue_name": "Blackheath Halls",  "zone": "South East",  "neighbourhood": "Blackheath",      "venue_tier": "1"},
    "Union Chapel":             {"venue_name": "Union Chapel",      "zone": "North",       "neighbourhood": "Islington",       "venue_tier": "1"},
}

# Halibuts venue names that are jams/non-gigs — skip
JAM_HINTS = {"jam session", "jam night", "open mic", "sit-in", "late late show"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

BASE_URL = "https://halibuts.com/genre/jazz"
MAX_PAGES = 30  # safety limit (~150 events per page default)


def fetch_page(page_num):
    url = f"{BASE_URL}/{page_num}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def parse_time(raw):
    """Normalise '7.45pm' / '19:45' / 'Doors open @ 6.00pm' → '7.45pm'"""
    raw = raw.strip()
    m = re.search(r'(\d{1,2})[:\.](\d{2})\s*(am|pm)', raw, re.I)
    if m:
        return f"{m.group(1)}.{m.group(2)}{m.group(3).lower()}"
    m = re.search(r'(\d{1,2}):(\d{2})', raw)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        suffix = "pm" if h >= 12 else "am"
        h12 = h if h <= 12 else h - 12
        return f"{h12}.{mn:02d}{suffix}"
    return raw


def parse_date(raw):
    """Parse 'Wednesday, 10 Jun 2026' → '2026-06-10'"""
    raw = re.sub(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s*', '', raw, flags=re.I)
    raw = raw.strip()
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def is_jam(title, description=""):
    tl = title.lower()
    dl = description.lower()
    return any(h in tl or h in dl for h in JAM_HINTS)


def parse_price(text):
    """Extract first price mention like £15"""
    m = re.search(r'£\d+(?:\.\d{2})?', text)
    return m.group(0) if m else ""


def make_gig_id(artist, venue, date_str):
    slug = re.sub(r'[^a-z0-9]+', '-', artist.lower()).strip('-')
    vslug = re.sub(r'[^a-z0-9]+', '-', venue.lower()).strip('-')
    return f"{slug}-{vslug}-{date_str}"


def scrape_halibuts():
    gigs = []
    seen_ids = set()
    today = date.today().isoformat()

    for page in range(1, MAX_PAGES + 1):
        html = fetch_page(page)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")

        # Each event is an <h2><a href="/events/eventdetail/..."> inside a card
        cards = soup.find_all("h2")
        found_on_page = 0

        for h2 in cards:
            a = h2.find("a", href=re.compile(r'/events/eventdetail/'))
            if not a:
                continue

            title = a.get_text(strip=True)
            detail_url = "https://halibuts.com" + a["href"]

            # Parse date + time from URL slug: ...-10-Jun-2026-7.45pm
            url_m = re.search(r'-(\d{1,2}-[A-Za-z]+-\d{4})-(\d{1,2}[.:]\d{2}(?:am|pm))', a["href"], re.I)
            if not url_m:
                continue

            raw_date = url_m.group(1).replace("-", " ")
            raw_time = url_m.group(2)

            date_str = parse_date(raw_date)
            if not date_str or date_str < today:
                continue

            time_str = parse_time(raw_time)

            # Find containing card div for venue + description
            card_div = h2.find_parent("div") or h2
            # Venue is in an h3 sibling
            venue_raw = ""
            for h3 in card_div.find_all("h3"):
                txt = h3.get_text(strip=True)
                if any(c.isalpha() for c in txt) and "Venue Details" not in txt:
                    venue_raw = re.split(r',\s*[A-Z]{1,2}\d', txt)[0].strip()
                    break

            # Strip [[Venue Details]] from venue name
            venue_raw = re.sub(r'\s*\[\[.*?\]\]', '', venue_raw).strip()

            venue_info = VENUE_MAP.get(venue_raw)
            if not venue_info:
                continue  # Only include known venues

            if is_jam(title):
                continue

            # Description — first <p> or descriptive text inside card
            desc = ""
            for p in card_div.find_all("p"):
                txt = p.get_text(strip=True)
                if len(txt) > 30 and "share" not in txt.lower():
                    desc = txt
                    break

            # Genres from card
            genre_tags = []
            for span in card_div.find_all(string=re.compile(r'^(Jazz|Swing|Blues|Soul|Electronic|R&B|Classical|Folk)$')):
                genre_tags.append(span.strip())

            gig_id = make_gig_id(title, venue_info["venue_name"], date_str)
            if gig_id in seen_ids:
                continue
            seen_ids.add(gig_id)
            found_on_page += 1

            gig = {
                "gig_id": gig_id,
                "date": date_str,
                "start_time": time_str,
                "artist_name": title,
                "venue_name": venue_info["venue_name"],
                "venue_tier": venue_info["venue_tier"],
                "zone": venue_info["zone"],
                "neighbourhood": venue_info["neighbourhood"],
                "ticket_url": detail_url,
                "price_from": parse_price(desc),
                "genre_tier1": "Jazz" if "Jazz" in genre_tags else (genre_tags[0] if genre_tags else "Jazz"),
                "format_tags": "Jazz Club",
                "description": desc[:300] if desc else "",
                "description_verified": False,
                "description_source": "halibuts",
                "special_occasion": "",
                "editors_pick": False,
                "hidden": False,
                "source": "halibuts",
            }
            gigs.append(gig)

        print(f"  Page {page}: {found_on_page} known-venue events found (total so far: {len(gigs)})")

        # If the page showed zero events at all (not just zero we kept), stop paginating
        if not cards or found_on_page == 0:
            # Check if there are ANY eventdetail links to know if we hit end
            all_links = soup.find_all("a", href=re.compile(r'/events/eventdetail/'))
            if not all_links:
                print(f"  No more events found, stopping at page {page}")
                break

    return gigs


if __name__ == "__main__":
    print("Scraping Halibuts...")
    results = scrape_halibuts()
    print(f"\nTotal gigs from Halibuts (known venues): {len(results)}")
    for g in results[:5]:
        print(f"  {g['date']} | {g['artist_name']} | {g['venue_name']} | {g['start_time']}")
    # Save locally for inspection
    with open("/home/claude/halibuts_preview.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to halibuts_preview.json")
