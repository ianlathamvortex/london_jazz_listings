"""
scraper_musicglue.py — MusicGlue venues (Karamel etc)
MusicGlue has a consistent API-style URL pattern making it reliable to scrape.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, fetch_json, gig, load, save, merge_gigs, clean_date, is_future

# All MusicGlue venues — add more here as discovered
MUSICGLUE_VENUES = {
    "karamel": {
        "venue_name": "Karamel",
        "zone":       "North",
        "hood":       "Wood Green",
        "url":        "https://www.musicglue.com/karamel",
        "format":     "Jazz Club",
        "genre":      "Contemporary Jazz",
    },
}


def scrape_venue(slug: str, info: dict) -> list:
    print(f"  Scraping MusicGlue: {info['venue_name']}...")
    base_url = info["url"]
    soup = fetch(base_url)
    if not soup:
        return []

    results = []

    # MusicGlue event URLs follow pattern: /venue-slug/events/YYYY-MM-DD-event-name
    event_links = soup.select(f"a[href*='/{slug}/events/']")
    seen = set()

    for link in event_links:
        href = link.get("href", "")
        if not href or href in seen:
            continue
        seen.add(href)

        full_url = href if href.startswith("http") else f"https://www.musicglue.com{href}"
        result = _scrape_event(full_url, info)
        if result and is_future(result["date"]):
            results.append(result)

    # Fallback: parse listing page directly
    if not results:
        results = _parse_listing(soup, info, base_url)

    return results


def _scrape_event(url: str, info: dict) -> dict | None:
    """Scrape individual MusicGlue event page."""
    soup = fetch(url)
    if not soup:
        return None

    text = soup.get_text(separator=" ", strip=True)

    # Artist/event name — MusicGlue puts it in h1
    h1 = soup.find("h1")
    artist = h1.get_text(strip=True) if h1 else ""
    if not artist:
        return None

    # Date — MusicGlue uses "Thu, Jun 4, 2026" format or similar
    date_patterns = [
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+(\w+ \d+,?\s+\d{4})",
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
    ]
    date_str = None
    for pattern in date_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            date_str = clean_date(m.group(0))
            break
    if not date_str:
        return None

    # Time
    time_m = re.search(r"(\d{1,2}:\d{2})\s*(pm|am|PM|AM)?", text)
    start_time = time_m.group(0) if time_m else ""

    # Doors
    doors_m = re.search(r"[Dd]oors?\s+open\s+(\d{1,2}[:.]\d{2})", text)
    doors_time = doors_m.group(1) if doors_m else ""

    # Price
    price_m = re.search(r"£(\d+)(?:\s*(?:Earlybird|General|Student|admission))?", text)
    price = f"£{price_m.group(1)}" if price_m else ""

    # Full price text — MusicGlue often lists multiple tiers
    price_full = ""
    price_tiers = re.findall(r"£\d+[^·\n]*?(?:Earlybird|General|Student|admission)", text)
    if price_tiers:
        price_full = " / ".join(price_tiers[:3])

    # Description from page
    desc_el = soup.find("div", class_=re.compile("description|about|info"))
    description = desc_el.get_text(separator=" ", strip=True)[:500] if desc_el else ""

    return gig(
        artist_name=artist,
        venue_name=info["venue_name"],
        date=date_str,
        start_time=start_time,
        doors_time=doors_time,
        price_from=price,
        price_full_text=price_full,
        ticket_url=url,
        source_url=url,
        zone=info["zone"],
        neighbourhood=info["hood"],
        format_tags=info["format"],
        genre_tier1=info["genre"],
        description=description,
    )


def _parse_listing(soup, info: dict, source_url: str) -> list:
    """Parse MusicGlue venue listing page directly."""
    results = []
    text = soup.get_text(separator="\n", strip=True)

    # Look for date + artist pairs
    date_pattern = re.compile(
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[,.]?\s+\w+\s+\d+[,.]?\s+\d{4}",
        re.IGNORECASE
    )

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    i = 0
    while i < len(lines):
        if date_pattern.search(lines[i]):
            date_str = clean_date(lines[i])
            # Next meaningful line is artist
            j = i + 1
            while j < len(lines) and len(lines[j]) < 3:
                j += 1
            artist = lines[j] if j < len(lines) else ""
            if artist and is_future(date_str):
                results.append(gig(
                    artist_name=artist,
                    venue_name=info["venue_name"],
                    date=date_str,
                    ticket_url=source_url,
                    source_url=source_url,
                    zone=info["zone"],
                    neighbourhood=info["hood"],
                    format_tags=info["format"],
                    genre_tier1=info["genre"],
                ))
            i = j + 1
        else:
            i += 1

    return results


def scrape() -> list:
    print("Scraping MusicGlue venues...")
    all_results = []
    for slug, info in MUSICGLUE_VENUES.items():
        results = scrape_venue(slug, info)
        all_results.extend(results)
        print(f"    {info['venue_name']}: {len(results)} gigs")
    print(f"  Total MusicGlue: {len(all_results)} gigs")
    return all_results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new MusicGlue gigs")


if __name__ == "__main__":
    run()
