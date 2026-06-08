"""
utils.py — shared helpers for all London Jazz scrapers
"""
import json
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── File paths ────────────────────────────────────────────────────────────
FILES = {
    "gigs":         DATA_DIR / "gigs.json",
    "jam_sessions": DATA_DIR / "jam_sessions.json",
    "brunches":     DATA_DIR / "brunches.json",
    "free_entry":   DATA_DIR / "free_entry.json",
    "festivals":    DATA_DIR / "festivals.json",
}

# ── Load / save ───────────────────────────────────────────────────────────
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

# ── Deduplication ─────────────────────────────────────────────────────────
def make_gig_id(artist: str, venue: str, date: str) -> str:
    raw = f"{artist.lower().strip()}-{venue.lower().strip()}-{date}"
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug[:80]

def merge_gigs(existing: list, new_gigs: list) -> tuple[list, int]:
    """Merge new gigs into existing, deduplicating by gig_id.
    Returns (merged_list, count_added)."""
    existing_ids = {g["gig_id"] for g in existing}
    added = 0
    for gig in new_gigs:
        if gig["gig_id"] not in existing_ids:
            existing.append(gig)
            existing_ids.add(gig["gig_id"])
            added += 1
        else:
            # Update fields that may have changed (price, time etc)
            for i, e in enumerate(existing):
                if e["gig_id"] == gig["gig_id"]:
                    existing[i].update({
                        k: v for k, v in gig.items()
                        if k not in ("description", "editors_pick",
                                     "editors_note", "star_rating")
                    })
                    existing[i]["last_updated"] = gig["last_updated"]
    return existing, added

# ── Date helpers ──────────────────────────────────────────────────────────
def clean_date(raw: str) -> str:
    """Try to return YYYY-MM-DD from messy date strings."""
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
        return True  # include if we can't parse

# ── HTTP ──────────────────────────────────────────────────────────────────
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
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

# ── Gig skeleton ──────────────────────────────────────────────────────────
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
