"""
scraper_gsmd.py — Guildhall School of Music & Drama (Milton Court / Silk Street)
Source: https://www.gsmd.ac.uk/whats-on?event_category=116  (Jazz category)
Reads the site's public JSON:API index, then each event page for time, venue, admission.
Free events -> free_entry.json; ticketed -> gigs.json.  Cadence: monthly (slow-moving).
"""
import re
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import requests
from bs4 import BeautifulSoup
from utils import gig, load, save, merge_gigs, is_future

BASE = "https://www.gsmd.ac.uk"
UA = {"User-Agent": "Mozilla/5.0"}
SKIP_TITLES = ("vangelis", "x efg london jazz festival", "efg london jazz festival")
Q = ("/jsonapi/index/site?page[limit]=50"
     "&filter[t][condition][path]=prefilter_type&filter[t][condition][operator]=IN"
     "&filter[t][condition][value][]=event"
     "&filter[d][condition][path]=prefilter_date_to&filter[d][condition][operator]=%3E="
     "&filter[d][condition][value][]={today}"
     "&filter[c][condition][path]=event_category&filter[c][condition][operator]=IN"
     "&filter[c][condition][value][]=116"
     "&sort[event_date][path]=event_date&sort[event_date][direction]=asc")


def _time(s):
    m = re.search(r"(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)", s, re.I)
    if not m:
        return ""
    h, mi, ap = int(m.group(1)), m.group(2) or "00", m.group(3).lower()
    if ap == "pm" and h < 12: h += 12
    if ap == "am" and h == 12: h = 0
    return f"{h:02d}:{mi}"


def _detail(path):
    try:
        r = requests.get(BASE + path, headers=UA, timeout=20)
        t = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
    except Exception:
        return "", "", False
    free = bool(re.search(r"Admission:\s*Free", t, re.I))
    t = re.sub(r"\s+", " ", t)
    m = re.search(r"Date, time and location:.{0,40}?\d{4}\s*,?\s*(\d{1,2}(?:[.:]\d{2})?\s*(?:am|pm))(?:\s*-\s*[\d.:]+\s*(?:am|pm))?\s+in\s+(Milton Court [A-Za-z ]*?(?:Hall|Theatre|Studio)|[A-Z][A-Za-z']+(?: [A-Z][A-Za-z']+){0,3})", t)
    start = _time(m.group(1)) if m else ""
    venue = m.group(2).strip() if m else ""
    return start, venue, free


def scrape():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        j = requests.get(BASE + Q.format(today=today), headers=UA, timeout=30).json()
    except Exception as e:
        print(f"  GSMD feed failed: {e}")
        return [], []
    paid, free = [], []
    for it in j.get("data", []):
        a = it.get("attributes", {})
        title = (a.get("title") or "").strip()
        if not title or any(s in title.lower() for s in SKIP_TITLES):
            continue
        date = (a.get("field_date_from") or "")[:10]
        if not date or not is_future(date) or a.get("field_cancelled_postponed"):
            continue
        path = (a.get("path") or {}).get("alias", "")
        start, stage, is_free = _detail(path) if path else ("", "", False)
        url = BASE + path
        g = gig(artist_name=title, venue_name="Milton Court", date=date,
                start_time=start, price_from="Free" if is_free else "",
                ticket_url=url, source_url=url, stage=stage,
                zone="Central", neighbourhood="Barbican",
                format_tags="Concert Hall", genre_tier1="Contemporary Jazz",
                venue_tier="2", special_occasion="")
        (free if is_free else paid).append(g)
    print(f"  GSMD: {len(paid)} ticketed, {len(free)} free")
    return paid, free


def run():
    paid, free = scrape()
    if paid:
        merged, added = merge_gigs(load("gigs"), paid)
        save("gigs", merged)
        print(f"  Added {added} new Guildhall gigs")
    if free:
        existing = load("free_entry")
        have = {(e.get("artist_name"), e.get("date"), e.get("venue_name")) for e in existing}
        n = 0
        for g in free:
            k = (g["artist_name"], g["date"], g["venue_name"])
            if k in have: continue
            e = dict(g)
            e["entry_id"] = "free-" + g["gig_id"]
            e["event_name"] = g["artist_name"]
            e["booking_url"] = g["ticket_url"]
            e["free_entry_type"] = "Free"
            existing.append(e); n += 1
        save("free_entry", existing)
        print(f"  Added {n} new Guildhall free events")


if __name__ == "__main__":
    p, f = scrape()
    for g in p + f:
        print(g["date"], g["start_time"], g["stage"], "|", g["price_from"])
