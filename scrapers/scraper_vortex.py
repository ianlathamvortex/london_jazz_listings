"""
scraper_vortex.py — Vortex Jazz Club, Dalston
Only returns ticketed gigs — skips jam sessions and recurring events.
Vortex is closed Mondays.
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, is_future

VENUE      = "Vortex Jazz Club"
ZONE       = "North"
HOOD       = "Dalston"
BASE_URL   = "https://www.vortexjazz.co.uk"
DAYS_AHEAD = 90

CLOSED_DAYS = {0}  # Monday

# Titles that are navigation elements, not events
NAV_TITLES = {
    "event views navigation", "find events", "previous day",
    "next day", "view as", "list month", "back to site",
    "dalston song club",  # not jazz
}

# These are recurring sessions — exclude from gigs, they're in jam_sessions.json
JAM_SESSION_NAMES = {
    "midweek downstairs jam",
    "vortex jam",
    "jam session",
    "open mic",
    "monthly jam",
    "weekly jam",
    "sunday jam",
    "jazz jam",
}


def _is_jam_session(title: str) -> bool:
    return any(j in title.lower() for j in JAM_SESSION_NAMES)


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    results = []
    today = datetime.now()
    seen_ids = set()

    for i in range(DAYS_AHEAD):
        date = today + timedelta(days=i)
        if date.weekday() in CLOSED_DAYS:
            continue

        date_str = date.strftime("%Y-%m-%d")
        url = f"{BASE_URL}/events/{date_str}/"
        day_gigs = _scrape_day(url, date_str)

        for g in day_gigs:
            if g["gig_id"] not in seen_ids:
                results.append(g)
                seen_ids.add(g["gig_id"])

    print(f"  Found {len(results)} future Vortex gigs")
    return results


def _scrape_day(url: str, date_str: str) -> list:
    soup = fetch(url)
    if not soup:
        return []

    event_articles = (
        soup.select("article.type-tribe_events") or
        soup.select("div.tribe-event") or
        []
    )

    if not event_articles:
        return []

    results = []
    for article in event_articles:
        result = _parse_article(article, date_str, url)
        if result:
            results.append(result)

    return results


def _parse_article(article, date_str: str, source_url: str) -> dict | None:
    from utils import gig as make_gig

    # Primary: real markup wraps the title in <a class="post_title"><h1>...</h1></a>
    # with no class on the h1 itself, so h2/h1.tribe-events selectors never
    # matched and every event was silently skipped. a.post_title gives us
    # both the title text and the href in one element.
    title_anchor = article.select_one("a.post_title")
    if title_anchor:
        artist = title_anchor.get_text(strip=True)
        href = title_anchor.get("href")
        ticket_url = href if href and href.startswith("http") else (BASE_URL + href if href else source_url)
    else:
        # Fallback for any other markup variant
        title_el = (
            article.find("h2", class_=re.compile("tribe-events")) or
            article.find("h1", class_=re.compile("tribe-events")) or
            article.find("h1") or
            article.find("h2") or
            article.find("h3")
        )
        if not title_el:
            return None
        artist = title_el.get_text(strip=True)
        link = title_el.find("a", href=True) or article.find("a", href=True)
        if link:
            href = link["href"]
            ticket_url = href if href.startswith("http") else BASE_URL + href
        else:
            ticket_url = source_url

    if not artist or len(artist) < 3:
        return None
    if artist.lower().strip() in NAV_TITLES:
        return None

    # Skip jam sessions
    if _is_jam_session(artist):
        return None

    text = article.get_text(separator=" ", strip=True)
    time_m  = re.search(r"(\d{1,2}[:.]\d{2})\s*(pm|am)?", text, re.I)
    price_m = re.search(r"£(\d+)", text)

    stage = ""
    if "downstairs" in text.lower():
        stage = "Downstairs"
    elif "upstairs" in text.lower():
        stage = "Upstairs"

    special = "Album launch" if "album launch" in text.lower() else ""

    return make_gig(
        artist_name=artist,
        venue_name=VENUE,
        date=date_str,
        start_time=time_m.group(0) if time_m else "19:45",
        price_from=f"£{price_m.group(1)}" if price_m else "",
        ticket_url=ticket_url,
        source_url=source_url,
        stage=stage,
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags="Jazz Club",
        genre_tier1="Contemporary Jazz",
        special_occasion=special,
    )


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Vortex gigs")


if __name__ == "__main__":
    run()
