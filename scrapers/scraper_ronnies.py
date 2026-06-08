"""
scraper_ronnies.py — Ronnie Scott's Jazz Club
Source: https://www.ronniescotts.co.uk/find-a-show
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, fetch_json, gig, load, save, merge_gigs, clean_date, is_future

VENUE       = "Ronnie Scott's"
ZONE        = "Central"
HOOD        = "Soho"
BASE_URL    = "https://www.ronniescotts.co.uk"
CALENDAR    = f"{BASE_URL}/find-a-show"
FORMAT      = "Jazz Club"

# Stage name → format tag / tier
STAGE_MAP = {
    "Main Show":        ("Main Stage",     "Jazz Club"),
    "Late Late Show":   ("Late Late Show", "Jazz Club"),
    "Late Late Show Upstairs": ("Late Late Show Upstairs", "Standing / Gig"),
    "Upstairs at Ronnie's":    ("Upstairs",               "Jazz Club"),
}


def scrape() -> list:
    print(f"Scraping {VENUE}...")
    soup = fetch(CALENDAR)
    if not soup:
        return []

    results = []

    # Ronnie's renders show listings as article/li blocks with data attributes
    # Try the show-calendar page which has cleaner structured markup
    soup2 = fetch(f"{BASE_URL}/show-calendar")
    target = soup2 or soup

    # Find all show entries — they use various class patterns across site updates
    # Try multiple selectors for resilience
    show_blocks = (
        target.select("div.show-listing") or
        target.select("article.show") or
        target.select("li.show-item") or
        target.select("div[class*='show']") or
        []
    )

    # Fallback: parse the text-based calendar table
    if not show_blocks:
        show_blocks = target.select("td.show-cell, div.calendar-show, div.event-item")

    if not show_blocks:
        print(f"  WARNING: No show blocks found — site structure may have changed")
        # Final fallback: scrape the upcoming shows list page
        results = _scrape_list_page(target)
        return results

    for block in show_blocks:
        try:
            result = _parse_block(block)
            if result and is_future(result["date"]):
                results.append(result)
        except Exception as e:
            print(f"  Parse error: {e}")
            continue

    print(f"  Found {len(results)} future gigs")
    return results


def _scrape_list_page(soup) -> list:
    """Parse the show listing page which uses a different layout."""
    results = []

    # Look for show entries in the main content area
    entries = soup.select("div.show, article, div[data-show]")
    if not entries:
        # Try finding by text patterns
        entries = soup.find_all(
            lambda tag: tag.name in ("div", "article", "li") and
            tag.get_text(strip=True) and
            any(kw in tag.get_text() for kw in
                ["Main Show", "Late Late", "Upstairs", "Jun", "Jul", "Aug"])
        )

    for entry in entries[:100]:  # cap at 100
        text = entry.get_text(separator=" ", strip=True)

        # Try to extract date
        date_match = re.search(
            r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
            text, re.IGNORECASE
        )
        if not date_match:
            continue

        date_str = clean_date(date_match.group(0))
        if not is_future(date_str):
            continue

        # Artist name — usually the first significant text before the date
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        artist = lines[0] if lines else "TBC"

        # Stage
        stage = "Main Stage"
        for s in STAGE_MAP:
            if s.lower() in text.lower():
                stage = s
                break

        # Link
        link_tag = entry.find("a", href=True)
        ticket_url = BASE_URL + link_tag["href"] if link_tag and link_tag["href"].startswith("/") else (link_tag["href"] if link_tag else CALENDAR)

        results.append(gig(
            artist_name=artist,
            venue_name=VENUE,
            date=date_str,
            ticket_url=ticket_url,
            source_url=CALENDAR,
            stage=stage,
            zone=ZONE,
            neighbourhood=HOOD,
            format_tags=STAGE_MAP.get(stage, ("", "Jazz Club"))[1],
            genre_tier1="Contemporary Jazz",
        ))

    return results


def _parse_block(block) -> dict | None:
    """Parse a single show block element."""
    text = block.get_text(separator=" ", strip=True)
    if not text:
        return None

    # Date
    date_match = re.search(
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if not date_match:
        return None
    date_str = clean_date(date_match.group(0))

    # Artist
    h_tag = block.find(["h1","h2","h3","h4","strong"])
    artist = h_tag.get_text(strip=True) if h_tag else text[:50]

    # Stage
    stage = "Main Stage"
    stage_format = "Jazz Club"
    for s, (_, fmt) in STAGE_MAP.items():
        if s.lower() in text.lower():
            stage = s
            stage_format = fmt
            break

    # Time
    time_match = re.search(r"(\d{1,2}[:\.]\d{2})\s*(pm|am)", text, re.IGNORECASE)
    start_time = time_match.group(0) if time_match else ""

    # Price
    price_match = re.search(r"£(\d+)", text)
    price = f"£{price_match.group(1)}" if price_match else ""

    # Ticket URL
    link = block.find("a", href=True)
    if link:
        href = link["href"]
        ticket_url = BASE_URL + href if href.startswith("/") else href
    else:
        ticket_url = CALENDAR

    return gig(
        artist_name=artist,
        venue_name=VENUE,
        date=date_str,
        start_time=start_time,
        ticket_url=ticket_url,
        source_url=CALENDAR,
        stage=stage,
        price_from=price,
        zone=ZONE,
        neighbourhood=HOOD,
        format_tags=stage_format,
        genre_tier1="Contemporary Jazz",
    )


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found — check site structure")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new Ronnie's gigs")


if __name__ == "__main__":
    run()
