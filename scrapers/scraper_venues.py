"""
scraper_venues.py — Generic scraper for smaller London jazz venues
Handles sites with standard HTML event listings.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

# Venue configurations
VENUES = {
    "east_side_jazz": {
        "name":   "East Side Jazz Club",
        "url":    "https://www.eastsidejazzclub.co.uk/upcoming-events/",
        "zone":   "East", "hood": "Leytonstone",
        "format": "Jazz Club", "genre": "Contemporary Jazz",
        "tier":   "1",
    },
    "green_note": {
        "name":   "Green Note",
        "url":    "https://www.greennote.co.uk/events-page/jazz/",
        "zone":   "North", "hood": "Camden",
        "format": "Standing / Gig", "genre": "Contemporary Jazz",
        "tier":   "1",
    },
    "toulouse_lautrec": {
        "name":   "Toulouse Lautrec",
        "url":    "https://toulouselautrec.co.uk/whats-on/",
        "zone":   "South East", "hood": "Brixton",
        "format": "Jazz Club", "genre": "Contemporary Jazz",
        "tier":   "1",
    },
    "olivers_jazz": {
        "name":   "Oliver's Jazz Bar",
        "url":    "https://oliversjazzbar.com/whats-on/",
        "zone":   "South East", "hood": "Greenwich",
        "format": "Jazz Club", "genre": "Contemporary Jazz",
        "tier":   "1",
    },
    "spice_of_life": {
        "name":   "Spice of Life Soho",
        "url":    "https://www.spiceoflifesoho.com/events/",
        "zone":   "Central", "hood": "Soho",
        "format": "Standing / Gig", "genre": "Contemporary Jazz",
        "tier":   "1",
    },
    "hampstead_jazz": {
        "name":   "Hampstead Jazz Club",
        "url":    "https://hampsteadjazzclub.com/whats-on/",
        "zone":   "North", "hood": "Hampstead",
        "format": "Jazz Club", "genre": "Mainstream / Swing",
        "tier":   "1",
    },
    "cafe_oto": {
        "name":   "Café OTO",
        "url":    "https://www.cafeoto.co.uk/events/",
        "zone":   "North", "hood": "Dalston",
        "format": "Standing / Gig", "genre": "Experimental / Free",
        "tier":   "1",
    },
    "grow_hackney": {
        "name":   "Grow Hackney",
        "url":    "https://www.growhackney.co.uk/jazz",
        "zone":   "East", "hood": "Hackney Wick",
        "format": "Standing / Gig", "genre": "Contemporary Jazz",
        "tier":   "1",
    },
    "jazz_cafe_posk": {
        "name":   "Jazz Café POSK",
        "url":    "https://jazzcafeposk.org/gig-guide/",
        "zone":   "West", "hood": "Hammersmith",
        "format": "Jazz Club", "genre": "Latin",
        "tier":   "1",
    },
    "ladbroke_hall": {
        "name":   "Ladbroke Hall",
        "url":    "https://ladbrokehall.com/live-programme/jazz/",
        "zone":   "West", "hood": "Notting Hill / Ladbroke Grove",
        "format": "Concert Hall", "genre": "Contemporary Jazz",
        "tier":   "1",
        "jazz_filter": True,
        "max_title_len": 70,
    },
    "cockpit": {
        "name":   "The Cockpit",
        "url":    "https://www.thecockpit.org.uk/show/jazz_in_the_round",
        "zone":   "North", "hood": "Camden",
        "format": "Concert Hall", "genre": "Contemporary Jazz",
        "tier":   "1",
    },
    "kings_place": {
        "name":   "King's Place",
        "url":    "https://www.kingsplace.co.uk/whats-on/jazz/",
        "zone":   "Central", "hood": "Barbican / City",
        "format": "Concert Hall", "genre": "Contemporary Jazz",
        "tier":   "2",
    },
    "rah_jazz": {
        "name":   "Royal Albert Hall",
        "url":    "https://www.royalalberthall.com/tickets/series/late-night-jazz",
        "zone":   "Central", "hood": "Piccadilly",
        "format": "Concert Hall", "genre": "Contemporary Jazz",
        "tier":   "2",
    },
    "wigmore": {
        "name":   "Wigmore Hall",
        "url":    "https://www.wigmore-hall.org.uk/whats-on",
        "zone":   "Central", "hood": "Piccadilly",
        "format": "Concert Hall", "genre": "Contemporary Jazz",
        "tier":   "2",
        "jazz_filter": True,  # needs additional jazz filtering
    },
}

# Jazz keywords for Tier 2 filtering
JAZZ_KEYWORDS = [
    "jazz", "improvisation", "improvised", "bebop", "bop", "swing",
    "blues", "soul", "latin jazz", "fusion", "quartet", "quintet",
    "trio", "sextet", "big band", "saxophone", "trumpet", "bass",
    "drums", "piano", "hammond", "electric piano", "afrobeat",
    "bossa nova", "samba", "coltrane", "miles davis", "monk",
    "ellington", "mingus", "ornette", "free jazz", "avant-garde",
]


def _is_jazz(text: str) -> bool:
    """Check if an event is jazz-related."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in JAZZ_KEYWORDS)


def scrape_venue(key: str, config: dict) -> list:
    """Generic scraper for a single venue."""
    print(f"  Scraping {config['name']}...")
    soup = fetch(config["url"])
    if not soup:
        return []

    results = []
    needs_jazz_filter = config.get("jazz_filter", False)

    # Strategy 1: Find event articles/cards
    event_blocks = (
        soup.select("article") or
        soup.select("div[class*='event']") or
        soup.select("li[class*='event']") or
        soup.select("div[class*='show']") or
        soup.select("div[class*='gig']") or
        []
    )

    # Strategy 2: Find event links
    if not event_blocks:
        base = config["url"].rstrip("/").rsplit("/", 1)[0]
        event_links = soup.select("a[href]")
        for link in event_links:
            href = link.get("href","")
            text = link.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            # Check for date-like patterns nearby
            parent_text = link.parent.get_text(strip=True) if link.parent else ""
            if re.search(r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", parent_text, re.I):
                if needs_jazz_filter and not _is_jazz(parent_text):
                    continue
                full_url = href if href.startswith("http") else base + "/" + href.lstrip("/")
                result = _scrape_event_page(full_url, config)
                if result and is_future(result["date"]):
                    results.append(result)
        return results

    for block in event_blocks:
        text = block.get_text(separator=" ", strip=True)
        if needs_jazz_filter and not _is_jazz(text):
            continue

        result = _parse_block(block, config)
        if result and is_future(result["date"]):
            results.append(result)

    print(f"    {config['name']}: {len(results)} gigs")
    return results


def _parse_block(block, config: dict) -> dict | None:
    text = block.get_text(separator=" ", strip=True)

    # Artist
    h = block.find(["h1","h2","h3","h4","strong"])
    artist = h.get_text(strip=True) if h else ""
    if not artist or len(artist) < 3:
        return None
    # Truncate concatenated title+description (scraper sometimes merges them)
    max_len = config.get("max_title_len", 120)
    if len(artist) > max_len:
        artist = artist[:max_len].rsplit(" ", 1)[0].strip()

    # Date
    date_m = re.search(
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)(?:\s+(\d{4}))?",
        text, re.IGNORECASE
    )
    if not date_m:
        return None
    year = date_m.group(3) or "2026"
    date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")

    # Time
    time_m = re.search(r"(\d{1,2}[:.]\d{2})\s*(pm|am)?", text, re.IGNORECASE)
    start_time = time_m.group(0) if time_m else ""

    # Price
    price_m = re.search(r"£(\d+)", text)
    price = f"£{price_m.group(1)}" if price_m else ""
    if any(p in text.lower() for p in ["free entry", "free admission", "admission free", "no charge", "free gig"]) and not price:
        price = "Free"

    # Ticket link
    link = block.find("a", href=True)
    href = link["href"] if link else ""
    base = config["url"].rstrip("/").rsplit("/", 1)[0]
    ticket_url = href if href.startswith("http") else (base + "/" + href.lstrip("/") if href else config["url"])

    # Special occasion
    special = ""
    text_lower = text.lower()
    if "album launch" in text_lower or "album release" in text_lower:
        special = "Album launch"
    elif "first uk" in text_lower or "first london" in text_lower:
        special = "Rare London appearance"

    return gig(
        artist_name=artist,
        venue_name=config["name"],
        date=date_str,
        start_time=start_time,
        price_from=price,
        ticket_url=ticket_url,
        source_url=config["url"],
        zone=config["zone"],
        neighbourhood=config["hood"],
        format_tags=config["format"],
        genre_tier1=config["genre"],
        venue_tier=config["tier"],
        special_occasion=special,
    )


def _scrape_event_page(url: str, config: dict) -> dict | None:
    """Scrape individual event page as fallback."""
    soup = fetch(url)
    if not soup:
        return None

    text = soup.get_text(separator=" ", strip=True)

    h1 = soup.find("h1")
    artist = h1.get_text(strip=True) if h1 else ""
    if not artist:
        return None

    date_m = re.search(
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)(?:\s+(\d{4}))?",
        text, re.IGNORECASE
    )
    if not date_m:
        return None
    year = date_m.group(3) or "2026"
    date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")

    time_m = re.search(r"(\d{1,2}[:.]\d{2})\s*(pm|am)", text, re.IGNORECASE)
    price_m = re.search(r"£(\d+)", text)

    return gig(
        artist_name=artist,
        venue_name=config["name"],
        date=date_str,
        start_time=time_m.group(0) if time_m else "",
        price_from=f"£{price_m.group(1)}" if price_m else "",
        ticket_url=url,
        source_url=url,
        zone=config["zone"],
        neighbourhood=config["hood"],
        format_tags=config["format"],
        genre_tier1=config["genre"],
        venue_tier=config["tier"],
    )


def scrape() -> list:
    print("Scraping smaller London venues...")
    all_results = []
    for key, config in VENUES.items():
        results = scrape_venue(key, config)
        all_results.extend(results)
    print(f"  Total smaller venues: {len(all_results)} gigs")
    return all_results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new gigs from smaller venues")


if __name__ == "__main__":
    run()
