"""
utils.py — shared helpers for all London Jazz scrapers
"""
import json
import re
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

FILES = {
    "gigs":         DATA_DIR / "gigs.json",
    "jam_sessions": DATA_DIR / "jam_sessions.json",
    "brunches":     DATA_DIR / "brunches.json",
    "free_entry":   DATA_DIR / "free_entry.json",
    "festivals":    DATA_DIR / "festivals.json",
}

def load(category: str) -> list:
    path = FILES[category]
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []

def save(category: str, records: list):
    path = FILES[category]
    with open(path, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"  Saved {len(records)} records → {path.name}")

def make_gig_id(artist: str, venue: str, date: str) -> str:
    raw = f"{artist.lower().strip()}-{venue.lower().strip()}-{date}"
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug[:80]

def _normalise(s: str) -> str:
    """Normalise string for fuzzy comparison."""
    s = s.lower().strip()
    # Remove common suffixes/prefixes that vary between sources
    s = re.sub(r"\s+(quartet|quintet|trio|duo|sextet|band|group|ensemble)$", "", s)
    s = re.sub(r"^(the|a|an)\s+", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s

def _is_near_duplicate(new_gig: dict, existing: dict) -> bool:
    """Check if two gigs are likely the same event from different sources."""
    if new_gig["date"] != existing["date"]:
        return False
    if new_gig["venue_name"] != existing["venue_name"]:
        return False
    # Normalise artist names for comparison
    new_artist = _normalise(new_gig["artist_name"])
    ex_artist  = _normalise(existing["artist_name"])
    if not new_artist or not ex_artist:
        return False
    # Check if one contains the other (handles "John Smith" vs "John Smith Quartet")
    if new_artist == ex_artist:
        return True
    if len(new_artist) > 8 and len(ex_artist) > 8:
        if new_artist in ex_artist or ex_artist in new_artist:
            return True
    return False

def merge_gigs(existing: list, new_gigs: list) -> tuple:
    """Merge new gigs, deduplicating by gig_id and near-duplicate detection."""
    existing_ids = {g["gig_id"] for g in existing}
    added = 0

    for new_gig in new_gigs:
        gig_id = new_gig["gig_id"]

        # Exact ID match — update non-editorial fields
        if gig_id in existing_ids:
            for i, e in enumerate(existing):
                if e["gig_id"] == gig_id:
                    existing[i].update({
                        k: v for k, v in new_gig.items()
                        if k not in ("description", "editors_pick",
                                     "editors_note", "star_rating")
                    })
                    existing[i]["last_updated"] = new_gig["last_updated"]
            continue

        # Near-duplicate check — same date, same venue, similar artist name
        is_dup = False
        for e in existing:
            if _is_near_duplicate(new_gig, e):
                is_dup = True
                break

        if not is_dup:
            existing.append(new_gig)
            existing_ids.add(gig_id)
            added += 1

    return existing, added

def clean_date(raw: str) -> str:
    from dateutil import parser as dp
    try:
        return dp.parse(raw, dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return raw.strip()

def is_future(date_str: str) -> bool:
    try:
        from dateutil import parser as dp
        return dp.parse(date_str) >= datetime.now()
    except Exception:
        return True

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

def fetch(url: str, timeout: int = 15) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None

def fetch_json(url: str, timeout: int = 15) -> dict | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ERROR fetching JSON {url}: {e}")
        return None

def gig(
    artist_name: str,
    venue_name: str,
    date: str,
    start_time: str = "",
    doors_time: str = "",
    price_from: str = "",
    price_full_text: str = "",
    ticket_url: str = "",
    source_url: str = "",
    stage: str = "",
    description: str = "",
    special_occasion: str = "",
    genre_tier1: str = "",
    genre_tier2: str = "",
    format_tags: str = "",
    zone: str = "",
    neighbourhood: str = "",
    venue_tier: str = "1",
) -> dict:
    return {
        "gig_id":           make_gig_id(artist_name, venue_name, date),
        "date":             date,
        "start_time":       start_time,
        "doors_time":       doors_time,
        "artist_name":      artist_name,
        "event_title":      "",
        "supporting_acts":  "",
        "venue_name":       venue_name,
        "venue_tier":       venue_tier,
        "stage":            stage,
        "zone":             zone,
        "neighbourhood":    neighbourhood,
        "ticket_url":       ticket_url,
        "price_from":       price_from,
        "price_full_text":  price_full_text,
        "genre_tier1":      genre_tier1,
        "genre_tier2":      genre_tier2,
        "format_tags":      format_tags,
        "description":      description,
        "special_occasion": special_occasion,
        "editors_pick":     False,
        "editors_note":     "",
        "star_rating":      "",
        "hidden":           False,
        "source_url":       source_url,
        "date_scraped":     datetime.now().strftime("%Y-%m-%d"),
        "last_updated":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "verified":         "Yes",
        "scraper_notes":    "",
    }


# ── Genre detection ───────────────────────────────────────────

GENRE_SIGNALS = {
    "Big Band":             ["big band", "orchestra", "swing", "count basie", "ellington", "benny goodman", "guy barker big band"],
    "Vocal & Standards":    ["vocal", "singer", "vocalist", "standards", "songbook", "cabaret", "crooner", "sinatra", "billie holiday", "ella fitzgerald"],
    "Latin":                ["latin", "salsa", "cuban", "afro-cuban", "mambo", "cha cha", "rumba", "timba"],
    "Brazilian / MPB":      ["brazil", "bossa nova", "samba", "mpb", "baiao", "caetano", "jobim", "gilberto", "brazilian"],
    "Soul & Groove":        ["soul", "groove", "r&b", "funk", "gospel", "motown", "incognito", "rhythm and blues"],
    "Experimental / Free":  ["free improv", "avant-garde", "experimental", "free jazz", "improvised music", "electroacoustic"],
    "Fusion":               ["fusion", "mahavishnu", "weather report", "herbie hancock", "miles electric", "electric"],
    "Trad / Dixieland":     ["dixieland", "trad jazz", "new orleans", "traditional jazz", "ragtime"],
    "Mainstream / Swing":   ["bebop", "hard bop", "swing", "mainstream", "standards", "quartet", "quintet", "blue note"],
    "African Jazz":         ["afrobeat", "african", "west african", "south african", "ethiopian", "ethio", "highlife"],
    "Sacred / Spiritual":   ["gospel", "sacred", "spiritual", "mass", "vespers", "church"],
    "Gypsy / Manouche":     ["gypsy", "manouche", "django", "romani", "jazz gitane"],
    "Indo-Jazz":            ["indian", "carnatic", "hindustani", "raga", "shakti", "tabla"],
    "Caribbean Jazz":       ["caribbean", "calypso", "steel pan", "reggae jazz", "ska jazz"],
}

def detect_genre(text: str) -> str:
    """Detect Tier 1 genre from event text."""
    text_lower = text.lower()
    for genre, signals in GENRE_SIGNALS.items():
        if any(s in text_lower for s in signals):
            return genre
    return "Contemporary Jazz"
