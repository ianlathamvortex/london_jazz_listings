"""
scraper_pizzaexpress.py — PizzaExpress Jazz Club (Soho + Pheasantry)
Source: https://www.pizzaexpresslive.com/whats-on
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, fetch_json, gig, load, save, merge_gigs, clean_date, is_future

VENUES = {
    "PizzaExpress Jazz Club (Soho)": {
        "zone": "Central", "hood": "Soho",
        "url_filter": "soho",
    },
    "PizzaExpress The Pheasantry": {
        "zone": "South West", "hood": "Chelsea / Lots Road",
        "url_filter": "pheasantry",
    },
}

BASE_URL = "https://www.pizzaexpresslive.com"
WHATS_ON = f"{BASE_URL}/whats-on"


def scrape() -> list:
    print("Scraping PizzaExpress Jazz...")
    soup = fetch(WHATS_ON)
    if not soup:
        return []

    results = []

    # PizzaExpress uses a React/Next.js frontend
    # Events are often in script tags as JSON or in data attributes
    # Try to find event data in script tags
    script_data = _extract_script_data(soup)
    if script_data:
        results = _parse_json_events(script_data)

    # Fallback: scrape visible HTML
    if not results:
        results = _parse_html(soup)

    print(f"  Found {len(results)} future PizzaExpress gigs")
    return results


def _extract_script_data(soup) -> list | None:
    """Try to extract JSON event data from Next.js __NEXT_DATA__ script."""
    import json
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        return None
    try:
        data = json.loads(script.string)
        # Navigate the Next.js page props structure
        props = data.get("props", {}).get("pageProps", {})
        events = (
            props.get("events") or
            props.get("shows") or
            props.get("listings") or
            []
        )
        return events if events else None
    except Exception:
        return None


def _parse_json_events(events: list) -> list:
    """Parse events from PizzaExpress JSON data."""
    results = []
    for event in events:
        try:
            artist = (
                event.get("name") or
                event.get("title") or
                event.get("artistName") or ""
            )
            if not artist:
                continue

            # Date/time
            date_raw = (
                event.get("date") or
                event.get("startDate") or
                event.get("dateTime") or ""
            )
            if not date_raw:
                continue
            date_str = clean_date(str(date_raw)[:10])
            if not is_future(date_str):
                continue

            # Venue
            venue_raw = (
                event.get("venue", {}).get("name", "") if isinstance(event.get("venue"), dict)
                else event.get("venueName", "")
            )
            venue_name = "PizzaExpress Jazz Club (Soho)"
            zone = "Central"
            hood = "Soho"
            for v, info in VENUES.items():
                if info["url_filter"] in venue_raw.lower():
                    venue_name = v
                    zone = info["zone"]
                    hood = info["hood"]
                    break

            # Price
            price = event.get("price") or event.get("priceFrom") or ""
            if price:
                price = f"£{price}" if not str(price).startswith("£") else str(price)

            # URL
            slug = event.get("slug") or event.get("url") or ""
            ticket_url = f"{BASE_URL}/whats-on/{slug}" if slug else WHATS_ON

            results.append(gig(
                artist_name=artist,
                venue_name=venue_name,
                date=date_str,
                price_from=str(price),
                ticket_url=ticket_url,
                source_url=WHATS_ON,
                zone=zone,
                neighbourhood=hood,
                format_tags="Jazz Club",
                genre_tier1="Contemporary Jazz",
            ))
        except Exception as e:
            print(f"  JSON parse error: {e}")
            continue
    return results


def _parse_html(soup) -> list:
    """Fallback HTML parsing for PizzaExpress."""
    results = []

    # Look for event cards
    cards = (
        soup.select("div[class*='event']") or
        soup.select("article[class*='show']") or
        soup.select("li[class*='listing']") or
        []
    )

    for card in cards:
        text = card.get_text(separator=" ", strip=True)

        date_m = re.search(
            r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"(?:\s+(\d{4}))?",
            text, re.IGNORECASE
        )
        if not date_m:
            continue

        year = date_m.group(3) or "2026"
        date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")
        if not is_future(date_str):
            continue

        h = card.find(["h1","h2","h3","h4"])
        artist = h.get_text(strip=True) if h else text[:50]

        link = card.find("a", href=True)
        href = link["href"] if link else ""
        ticket_url = BASE_URL + href if href.startswith("/") else (href or WHATS_ON)

        # Determine venue
        venue_name = "PizzaExpress Jazz Club (Soho)"
        zone, hood = "Central", "Soho"
        for v, info in VENUES.items():
            if info["url_filter"] in text.lower() or info["url_filter"] in href.lower():
                venue_name = v
                zone = info["zone"]
                hood = info["hood"]
                break

        price_m = re.search(r"£(\d+)", text)
        price = f"£{price_m.group(1)}" if price_m else ""

        results.append(gig(
            artist_name=artist,
            venue_name=venue_name,
            date=date_str,
            price_from=price,
            ticket_url=ticket_url,
            source_url=WHATS_ON,
            zone=zone,
            neighbourhood=hood,
            format_tags="Jazz Club",
            genre_tier1="Contemporary Jazz",
        ))

    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new PizzaExpress gigs")


if __name__ == "__main__":
    run()
