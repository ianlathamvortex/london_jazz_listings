"""
enricher.py — Claude API description generator with web search
Runs nightly.
Reports coverage stats so the workflow can warn on gaps.
"""
import os
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))
from utils import load, save
from datetime import datetime

MODEL       = "claude-sonnet-4-6"
MAX_TOKENS  = 400

BAD_PATTERNS = [
    "no relevant results", "no specific", "couldn't find", "could not find",
    "i couldn't", "i could not", "unfortunately", "let me try",
    "more targeted search", "based on my search", "my search",
    "i found no", "i was unable", "unable to find", "i searched",
    "here is the listing description", "here\'s the description",
    "after searching", "search results",
]

SYSTEM_PROMPT = """You write short jazz gig descriptions for a London listings website.

PROCESS:
1. Search the web for the artist
2. Find ONE specific verifiable fact: named album + label, specific famous collaborator, award, country of origin
3. Write exactly 2 sentences, under 55 words, using ONLY facts you found

CRITICAL RULES:
- If you cannot find specific facts, respond with exactly: SKIP
- Never write about your search process
- Never say "jazz"
- Never start with the artist name
- Banned: "rarely does", "make you forget", "most compelling young", generic praise
- No preamble — just the text or SKIP"""


def _is_bad(text):
    t = text.lower()
    return any(p in t for p in BAD_PATTERNS)


def generate_description(artist, venue, date, special=""):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        prompt = f"Artist: {artist}\nVenue: {venue}, London\nDate: {date}"
        if special:
            prompt += f"\nOccasion: {special}"
        prompt += "\n\nWrite the description or SKIP:"
        msg = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": prompt}]
        )
        # Answer = text after the last web-search result (earlier text is preamble)
        last = max([i for i, b in enumerate(msg.content) if getattr(b, "type", "") == "web_search_tool_result"], default=-1)
        text = "".join(b.text for b in msg.content[last+1:] if getattr(b, "type", "") == "text").strip()
        text = re.sub(r"\s+([,.;:])", r"\1", text); text = re.sub(r"\s+", " ", text).replace("*", "")
        low = text.lower()
        if (not text or text.upper().startswith("SKIP") or _is_bad(text) or len(text) < 20
                or len(text.split()) > 60 or "jazz" in low or re.search(r"\b(tonight|this evening)\b", low)):
            return ""
        return text
    except Exception as e:
        print(f"  API error for {artist}: {e}")
        return ""


LEAK_PHRASES = ["no relevant results", "let me try", "more targeted search",
                "let me search", "couldn't find", "unable to find", "based on my search"]
TIME_BUDGET = 30 * 60   # seconds; workflow timeout is 45 min
WORKERS = 6


NOTE_VESPERS = ("Part of a light evening service at the American International Church, "
               "broadly suitable for people of any religion or belief.")


def _with_note(g):
    """Description for the free page; Vespers/Carols get a note that they are part of a light service."""
    d = (g.get("description") or "").strip()
    if g.get("venue_name", "").lower() == "american international church":
        if NOTE_VESPERS not in d:
            d = (d + " " + NOTE_VESPERS).strip()
    return d


def _tidy(records):
    """Blank leaked model text; move free-priced gigs to free_entry.json."""
    cleared = 0
    for r in records:
        d = r.get("description", "").lower()
        if d and any(p in d for p in LEAK_PHRASES):
            r["description"] = ""; r["description_verified"] = False; r["description_source"] = ""
            cleared += 1
    free = [r for r in records if r.get("price_from", "").strip().lower() == "free"]
    if free:
        fe = load("free_entry")
        have = {(e.get("artist_name") or e.get("event_name"), e.get("date")) for e in fe}
        for g in free:
            if (g.get("artist_name"), g.get("date")) in have:
                continue
            fe.append({"entry_id": "free-" + str(g.get("gig_id", "")), "event_name": g.get("artist_name", ""),
                       "artist_name": g.get("artist_name", ""), "venue_name": g.get("venue_name", ""),
                       "address": g.get("address", ""), "postcode": g.get("postcode", ""),
                       "zone": g.get("zone", ""), "neighbourhood": g.get("neighbourhood", ""),
                       "nearest_tube": g.get("nearest_tube", ""), "venue_type": "", "date": g.get("date", ""),
                       "start_time": g.get("start_time", ""), "end_time": "", "frequency": "",
                       "booking_required": False, "booking_url": g.get("ticket_url", ""),
                       "free_entry_type": "Free", "genre_tier1": g.get("genre_tier1", ""),
                       "format_tags": g.get("format_tags", ""), "description": _with_note(g),
                       "source_url": g.get("ticket_url", ""), "editors_pick": False, "hidden": False,
                       "last_verified": datetime.now().strftime("%Y-%m-%d")})
        save("free_entry", fe)
        records = [r for r in records if r not in free]
    print(f"  Tidy: cleared {cleared} leaked descriptions, moved {len(free)} free gigs")
    return records


def _apply_overrides(records):
    """Apply manual corrections from data/overrides.json (match on exact fields, then set fields)."""
    import json
    path = Path(__file__).parent.parent / "data" / "overrides.json"
    try:
        rules = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return records
    n = 0
    for r in records:
        for rule in rules:
            match = rule.get("match", {})
            if match and all(r.get(k) == v for k, v in match.items()):
                r.update(rule.get("set", {}))
                n += 1
    print(f"  Overrides applied: {n}")
    return records


def run():
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if not os.environ.get("ANTHROPIC_API_KEY", ""):
        print("  ANTHROPIC_API_KEY not set - skipping")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    records = _apply_overrides(_tidy(load("gigs")))
    future = [r for r in records if r.get("date", "") >= today]
    todo = [r for r in future if not r.get("description", "").strip() and r.get("artist_name") and r.get("venue_name")]
    print(f"Description coverage: {len(future) - len(todo)}/{len(future)}")

    # One lookup per artist (PizzaExpress repeats acts across many dates)
    first = {}
    for r in todo:
        first.setdefault(r["artist_name"], r)
    artists = list(first)
    print(f"  Researching {len(artists)} artists with {WORKERS} workers")

    results = {}
    start = time.time()
    ex = ThreadPoolExecutor(WORKERS)
    futs = {ex.submit(generate_description, a, first[a]["venue_name"], first[a]["date"],
                      first[a].get("special_occasion", "")): a for a in artists}
    try:
        for f in as_completed(futs, timeout=TIME_BUDGET):
            results[futs[f]] = f.result()
    except Exception as e:
        print(f"  Time budget reached ({e.__class__.__name__}) - saving what we have")
    ex.shutdown(wait=False, cancel_futures=True)

    count = 0
    for r in todo:
        d = results.get(r["artist_name"], "")
        if d:
            r["description"] = d
            r["description_verified"] = False
            r["description_source"] = "auto"
            count += 1
    save("gigs", records)
    got = sum(1 for v in results.values() if v)
    print(f"  Artists done {len(results)}/{len(artists)}, described {got}; gigs updated {count}; {int(time.time()-start)}s")
    future2 = [r for r in records if r.get("date", "") >= today]
    have2 = [r for r in future2 if r.get("description", "").strip()]
    print(f"  Final coverage: {len(have2)}/{len(future2)} ({100*len(have2)//max(len(future2),1)}%)")


if __name__ == "__main__":
    run()
