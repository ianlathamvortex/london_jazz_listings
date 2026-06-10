"""
scraper_pizzaexpress.py — PizzaExpress Jazz Club (Soho + Pheasantry)
Source: https://www.pizzaexpresslive.com/whats-on

PizzaExpress blocks all plain HTTP requests (403). Requires Playwright.
The site is Next.js — after JS renders, events appear as article/card elements.
Also tries __NEXT_DATA__ JSON blob which is faster when available.
"""

import re
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import gig, load, save, merge_gigs, clean_date, is_future
from browser import fetch_browser, fetch_browser_json, PLAYWRIGHT_AVAILABLE

BASE_URL  = "https://www.pizzaexpresslive.com"
WHATS_ON  = f"{BASE_URL}/whats-on"

VENUES = {
    "soho":        ("PizzaExpress Jazz Club", "Central",    "Soho",             "2"),
    "pheasantry":  ("PizzaExpress The Pheasantry", "South West", "Chelsea", "2"),
}


def _venue_from_url(href: str):
    hl = href.lower()
    for key, val in VENUES.items():
        if key in hl:
            return val
    return VENUES["soho"]   # default


def _parse_price(text: str) -> str:
    m = re.search(r"£(\d+(?:\.\d{2})?)", text)
    return f"£{m.group(1)}" if m else ""


def scrape() -> list:
    print("Scraping PizzaExpress Jazz (Playwright)...")
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available — skipping")
        return []

    soup = fetch_browser(
        WHATS_ON,
        wait_for="article, [class*=\'event\'], [class*=\'show\'], [class*=\'listing\']",
        timeout=40000,
    )
    if not soup:
        print("  No response from PizzaExpress")
        return []

    results = []

    # Strategy 1: __NEXT_DATA__ JSON blob (fastest, most reliable)
    script = soup.find("script", id="__NEXT_DATA__")
    if script:
        try:
            data = json.loads(script.string)
            props = data.get("props", {}).get("pageProps", {})
            events = (
                props.get("events") or
                props.get("shows") or
                props.get("listings") or
                props.get("data", {}).get("events") or
                []
            )
            if events:
                print(f"  Found {len(events)} events in __NEXT_DATA__")
                for ev in events:
                    artist = (ev.get("name") or ev.get("title") or ev.get("artistName") or "").strip()
                    if not artist:
                        continue
                    date_raw = ev.get("date") or ev.get("startDate") or ev.get("dateTime") or ""
                    date_str = clean_date(str(date_raw)[:10]) if date_raw else ""
                    if not date_str or not is_future(date_str):
                        continue
                    slug = ev.get("slug") or ev.get("url") or ""
                    href = f"/whats-on/{slug}" if slug and not slug.startswith("http") else slug
                    venue_name, zone, hood, tier = _venue_from_url(href)
                    price_raw = ev.get("price") or ev.get("priceFrom") or ""
                    price = f"£{price_raw}" if price_raw and not str(price_raw).startswith("£") else str(price_raw)
                    ticket_url = BASE_URL + href if href.startswith("/") else (href or WHATS_ON)
                    results.append(gig(
                        artist_name=artist, venue_name=venue_name, date=date_str,
                        price_from=price, ticket_url=ticket_url, source_url=WHATS_ON,
                        zone=zone, neighbourhood=hood, venue_tier=tier,
                        format_tags="Jazz Club", genre_tier1="Contemporary Jazz",
                    ))
                if results:
                    print(f"  Parsed {len(results)} future gigs from JSON")
                    return results
        except Exception as e:
            print(f"  __NEXT_DATA__ parse error: {e}")

    # Strategy 2: Parse rendered HTML cards
    selectors = [
        "article",
        "[class*=\'EventCard\']",
        "[class*=\'event-card\']",
        "[class*=\'show-card\']",
        "[class*=\'listing-item\']",
        "li[class*=\'event\']",
    ]
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    print(f"  Found {len(cards)} HTML cards")
    for card in cards:
        text = card.get_text(separator=" ", strip=True)
        link = card.find("a", href=re.compile(r"/whats-on/"))
        href = link["href"] if link else ""
        if not href:
            continue

        # Artist name
        h = card.find(["h1","h2","h3","h4"])
        artist = h.get_text(strip=True) if h else ""
        if not artist:
            # Try data attribute or first substantial text
            artist = card.get("data-name") or card.get("aria-label") or ""
        if not artist or len(artist) < 3:
            continue

        # Date
        date_m = re.search(
            r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
            r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
            r"Nov(?:ember)?|Dec(?:ember)?)(?:\s+(\d{4}))?",
            text, re.IGNORECASE
        )
        if not date_m:
            continue
        year = date_m.group(3) or "2026"
        date_str = clean_date(f"{date_m.group(1)} {date_m.group(2)} {year}")
        if not is_future(date_str):
            continue

        venue_name, zone, hood, tier = _venue_from_url(href)
        price = _parse_price(text)
        ticket_url = BASE_URL + href if href.startswith("/") else href

        results.append(gig(
            artist_name=artist, venue_name=venue_name, date=date_str,
            price_from=price, ticket_url=ticket_url, source_url=WHATS_ON,
            zone=zone, neighbourhood=hood, venue_tier=tier,
            format_tags="Jazz Club", genre_tier1="Contemporary Jazz",
        ))

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
