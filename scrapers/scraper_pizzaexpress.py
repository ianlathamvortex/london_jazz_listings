"""
scraper_pizzaexpress.py — PizzaExpress Live (Soho, Pheasantry, Holborn, Leicester Square)
Source: https://api.pizzaexpresslive.com/products/search-event-information

Site rebranded to "PizzaExpress Live" and moved to a fully client-rendered
Next.js frontend (no data in initial HTML, no __NEXT_DATA__ events blob).
Discovered via DevTools Network tab that the frontend calls this public JSON
API directly (Symfony API Platform / hydra format) — no auth required.
This replaces the old Playwright-based scraper which returned 0 results
after the rebrand broke every DOM selector it relied on.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, is_future, HEADERS
import requests

API_URL = "https://api.pizzaexpresslive.com/products/search-event-information"
WHATS_ON_URL = "https://www.pizzaexpresslive.com/whats-on"

# location (from API) -> (venue_name, zone, neighbourhood, venue_tier)
VENUES = {
    "soho":             ("PizzaExpress Live Soho",            "Central",    "Soho",             "1"),
    "chelsea":          ("PizzaExpress Live The Pheasantry",   "South West", "Chelsea",          "2"),
    "holborn":          ("PizzaExpress Live Holborn",          "Central",    "Holborn",          "2"),
    "leicester square": ("PizzaExpress Live Leicester Square", "Central",    "Leicester Square", "2"),
}


def _venue_info(location: str):
    key = (location or "").strip().lower()
    return VENUES.get(key, (f"PizzaExpress Live {location}".strip(), "Central", location or "", "2"))


def _parse_event_date(raw: str) -> str:
    """API gives dates like 'Saturday 4th July' with no year. Assume current
    year, but roll forward to next year if that would put it > ~2 months
    in the past (handles year-end -> new-year rollover)."""
    from dateutil import parser as dp
    if not raw:
        return ""
    try:
        dt = dp.parse(raw, dayfirst=True, default=datetime.now())
        if dt < datetime.now() - timedelta(days=60):
            dt = dt.replace(year=dt.year + 1)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def _parse_time(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip().replace("AM", "am").replace("PM", "pm")
    # "1:00pm" -> "1.00pm" to match site convention (e.g. "7.45pm")
    return raw.replace(":", ".")


def _parse_price(pence) -> str:
    try:
        pounds = int(pence) / 100
        if pounds <= 0:
            return ""
        return f"£{pounds:.0f}" if pounds == int(pounds) else f"£{pounds:.2f}"
    except (TypeError, ValueError):
        return ""


def scrape() -> list:
    print("Scraping PizzaExpress Live (JSON API)...")
    results = []
    page = 1
    seen_ids = set()

    while True:
        try:
            resp = requests.get(
                API_URL,
                params={"page": page, "itemsPerPage": 100, "expandDates": "false"},
                headers=HEADERS,
                timeout=20,
            )
        except requests.RequestException as e:
            print(f"  Request error on page {page}: {e}")
            break

        if resp.status_code != 200:
            print(f"  Page {page} returned HTTP {resp.status_code}")
            break

        data = resp.json()
        members = data.get("hydra:member", [])
        total = data.get("hydra:totalItems", 0)
        if not members:
            break

        for ev in members:
            eid = ev.get("id")
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            artist = (ev.get("name") or "").strip()
            if not artist:
                continue

            date_str = _parse_event_date(ev.get("eventDate", ""))
            if not date_str or not is_future(date_str):
                continue

            venue_name, zone, hood, tier = _venue_info(ev.get("location", ""))
            slug = ev.get("slug", "")
            ticket_url = f"{WHATS_ON_URL}/{slug}" if slug else WHATS_ON_URL

            results.append(gig(
                artist_name=artist,
                venue_name=venue_name,
                date=date_str,
                start_time=_parse_time(ev.get("showStartTime", "")),
                doors_time=_parse_time(ev.get("doorsOpenTime", "")),
                price_from=_parse_price(ev.get("price")),
                ticket_url=ticket_url,
                source_url=WHATS_ON_URL,
                zone=zone,
                neighbourhood=hood,
                venue_tier=tier,
                format_tags="Jazz Club",
                genre_tier1="Contemporary Jazz",
            ))

        if page * 100 >= total:
            break
        page += 1

    print(f"  Found {len(results)} future PizzaExpress gigs")
    return results


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No PizzaExpress gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new PizzaExpress gigs")


if __name__ == "__main__":
    run()
