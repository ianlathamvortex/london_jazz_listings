"""
scraper_musicglue.py — MusicGlue venues (Karamel etc)
Includes jazz keyword filtering to exclude non-jazz events.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

MUSICGLUE_VENUES = {
    "karamel": {
        "venue_name": "Karamel",
        "zone":       "North",
        "hood":       "Wood Green",
        "url":        "https://www.musicglue.com/karamel",
        "format":     "Jazz Club",
        "genre":      "Contemporary Jazz",
        "venue_tier": "2",
        "jazz_filter": True,
    },
    "the-bulls-head": {
        "venue_name": "Bull's Head Barnes",
        "zone":       "West / South West",
        "hood":       "Barnes",
        "url":        "https://tickets.thebullsheadbarnes.com/live-music",
        "format":     "Jazz Club",
        "genre":      "Mainstream / Swing",
        "jazz_filter": False,
    },
}

# Jazz keywords — event must match at least one
JAZZ_KEYWORDS = [
    "jazz", "improvisation", "improvised", "bebop", "swing", "blues",
    "quartet", "quintet", "trio", "sextet", "big band", "saxophone",
    "trumpet", "double bass", "hammond", "latin jazz", "fusion",
    "bossa nova", "samba", "afrobeat", "soul", "groove", "funk",
    "still waters", "collage presents", "henry lowther", "vortex",
    "tomorrow's warriors", "gary crosby", "jam session",
]

# Non-jazz keywords — exclude if matched
EXCLUDE_KEYWORDS = [
    "comedy", "spoken word", "poetry", "talk", "lecture", "workshop",
    "visual language", "exhibition", "conversation", "dance class",
    "yoga", "film", "cinema", "theatre", "theater", "opera",
    "classical guitar", "string quartet", "choral", "choir",
    "finding one's voice", "reflection", "career",
]


def _is_jazz(text: str) -> bool:
    """Return True if event appears jazz-related."""
    text_lower = text.lower()
    # Exclude clearly non-jazz
    if any(kw in text_lower for kw in EXCLUDE_KEYWORDS):
        return False
    # Include if jazz keyword found
    if any(kw in text_lower for kw in JAZZ_KEYWORDS):
        return True
    # For Karamel specifically, "Collage presents" is always jazz
    if "collage presents" in text_lower:
        return True
    return False


def scrape_venue(slug: str, info: dict) -> list:
    print(f"  Scraping MusicGlue: {info['venue_name']}...")
    base_url = info["url"]
    soup = fetch(base_url)
    if not soup:
        return []

    results = []
    event_links = soup.select(f"a[href*='/{slug}/events/']")
    seen = set()

    for link in event_links:
        href = link.get("href", "")
        if not href or href in seen:
            continue
        seen.add(href)

        # Quick check on link text before fetching full page
        link_text = link.get_text(strip=True)
        if link_text and not _is_jazz(link_text):
            # Check parent context too
            parent_text = link.parent.get_text(strip=True) if link.parent else ""
            if not _is_jazz(parent_text):
                continue

        full_url = href if href.startswith("http") else f"https://www.musicglue.com{href}"
        result = _scrape_event(full_url, info)
        if result and is_future(result["date"]):
            results.append(result)

    if not results:
        results = _parse_listing(soup, info, base_url)

    return results


def _scrape_event(url: str, info: dict) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    text = soup.get_text(separator=" ", strip=True)

    # Filter non-jazz events
    if not _is_jazz(text):
        return None

    h1 = soup.find("h1")
    artist = h1.get_text(strip=True) if h1 else ""
    if not artist:
        return None

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

    time_m  = re.search(r"(\d{1,2}:\d{2})\s*(pm|am|PM|AM)?", text)
    doors_m = re.search(r"[Dd]oors?\s+open\s+(\d{1,2}[:.]\d{2})", text)
    price_m = re.search(r"£(\d+)(?:\s*(?:Earlybird|General|Student|admission))?", text)

    price_tiers = re.findall(
        r"£\d+[^·\n]*?(?:Earlybird|General|Student|admission)", text
    )
    price_full = " / ".join(price_tiers[:3]) if price_tiers else ""

    desc_el = soup.find("div", class_=re.compile("description|about|info"))
    description = desc_el.get_text(separator=" ", strip=True)[:500] if desc_el else ""

    special = ""
    if "album launch" in text.lower():
        special = "Album launch"

    return gig(
        artist_name=artist,
        venue_name=info["venue_name"],
        date=date_str,
        start_time=time_m.group(0) if time_m else "",
        doors_time=doors_m.group(1) if doors_m else "",
        price_from=f"£{price_m.group(1)}" if price_m else "",
        price_full_text=price_full,
        ticket_url=url,
        source_url=url,
        zone=info["zone"],
        neighbourhood=info["hood"],
        format_tags=info["format"],
        genre_tier1=info["genre"],
        description=description,
        special_occasion=special,
    )


def _parse_listing(soup, info: dict, source_url: str) -> list:
    results = []
    text = soup.get_text(separator="\n", strip=True)
    date_pattern = re.compile(
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[,.]?\s+\w+\s+\d+[,.]?\s+\d{4}",
        re.IGNORECASE
    )
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    i = 0
    while i < len(lines):
        if date_pattern.search(lines[i]):
            date_str = clean_date(lines[i])
            j = i + 1
            while j < len(lines) and len(lines[j]) < 3:
                j += 1
            artist = lines[j] if j < len(lines) else ""
            context = " ".join(lines[max(0,j-2):j+3])
            if artist and is_future(date_str) and _is_jazz(artist + " " + context):
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
        print(f"    {info['venue_name']}: {len(results)} jazz gigs")
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
