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
    return any(p in t for p in BAD_PATTERNS) or bool(LEAK_RE.search(text))


def _clean(text):
    text = re.sub(r"\s+([,.;:])", r"\1", text); text = re.sub(r"\s+", " ", text).replace("*", "")
    return text.strip()


def _check(text):
    """Return '' if publishable, else the reason it was rejected."""
    low = text.lower()
    if not text or text.upper().startswith("SKIP") or len(text) < 20:
        return "skip"
    if _is_bad(text):
        return "leak"
    if "jazz" in low:
        return "jazz"
    if len(text.split()) > 60 or re.search(r"\b(tonight|this evening)\b", low):
        return "form"
    return ""


def _ask(client, artist, venue, date, special, uses, hint=""):
    prompt = f"Artist: {artist}\nVenue: {venue}, London\nDate: {date}"
    if special:
        prompt += f"\nOccasion: {special}"
    if hint:
        prompt += "\n\n" + hint
    prompt += "\n\nWrite the description or SKIP:"
    msg = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": uses}],
        messages=[{"role": "user", "content": prompt}])
    last = max([i for i, b in enumerate(msg.content) if getattr(b, "type", "") == "web_search_tool_result"], default=-1)
    return _clean("".join(b.text for b in msg.content[last+1:] if getattr(b, "type", "") == "text"))


def _rewrite(client, draft, why):
    """No search: fix wording of a draft that failed a form check, keeping only facts already in it."""
    fix = {"jazz": 'Remove the word "jazz" everywhere. If it sits inside a proper name (a festival, prize, band or album), rephrase so the name is not needed (e.g. "a major international trumpet competition") rather than deleting the word from the name. Never alter or drop any fact.',
           "form": "Cut to two sentences, under 55 words, and remove any reference to tonight or this evening."}[why]
    msg = client.messages.create(
        model=MODEL, max_tokens=300,
        system="You edit short gig blurbs. Keep ONLY the facts in the draft; add nothing. Output only the edited text, no preamble.",
        messages=[{"role": "user", "content": f"{fix} Do not start with the artist name.\n\nDraft: {draft}"}])
    return _clean("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))


def _from_listing(client, artist, venue, extra):
    """Last resort: one factual line built ONLY from the listing's own fields. Returns '' if nothing to say."""
    msg = client.messages.create(
        model=MODEL, max_tokens=150,
        system=("You write one short factual line for a London gig listing using ONLY the listing fields given. "
                "State only what the fields say (format, tribute subject, line-up, occasion, guests, venue session). "
                "Add nothing from your own knowledge. Never say jazz, never start with the artist name, no praise, "
                "no 'tonight'. Under 25 words. If the fields say nothing beyond a name, reply exactly: SKIP"),
        messages=[{"role": "user", "content": f"Artist/title: {artist}\nVenue: {venue}\n{extra}"}])
    return _clean("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))


def generate_description(artist, venue, date, special="", extra=""):
    """Up to 3 stages: search; on a wording failure rewrite the draft; on SKIP search again, harder."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        text = _ask(client, artist, venue, date, special, 3)
        why = _check(text)
        if why in ("jazz", "form"):
            text = _rewrite(client, text, why)
            why = _check(text)
        first_why, first_text = why, text
        if why in ("skip", "leak"):
            text = _ask(client, artist, venue, date, special, 5,
                        "A first search found nothing usable. Try Wikipedia, AllMusic, the label or the artist's own site, "
                        "and the venue listing. One concrete fact is enough: a named album and year, a band they lead or "
                        "play in, a notable collaborator, an award, or where they are from.")
            why = _check(text)
            if why in ("jazz", "form"):
                text = _rewrite(client, text, why)
                why = _check(text)
        if why:
            text = _from_listing(client, artist, venue, extra)
            why = _check(text)
            if why:
                print(f"  NO BLURB {artist}: first={first_why!r} {first_text[:90]!r} | listing={why!r} {text[:60]!r}")
                return ""
            return "\x00" + text   # marker: listing-derived
        return text
    except Exception as e:
        print(f"  API error for {artist}: {e}")
        return ""


# Model reasoning that must never reach the site (applies to auto descriptions only)
LEAK_RE = re.compile(r'''(^\W*(i |i'|no |now i|here is|here's|this is not|this artist|the search|the results|skip\b|\*\*skip)|verifiable|\bi cannot\b|\bi could not\b|\bi can't\b|\bi couldn't\b|\bi found\b|\bi have\b|\bi'll\b|search result|per my instr|artist name must|here is the (listing )?description|not a jazz|not a named|generic event title|\blet me\b|results (point|appear|pull)|\bi need to\b|\bi now\b)''', re.I)
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
        if d and r.get("description_source") != "manual" and LEAK_RE.search(r.get("description", "")):
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


def _repair_jazz(records, today):
    """Rewrite any live blurb containing the word jazz (facts kept), once per distinct text."""
    todo = [r for r in records if r.get("date", "") >= today and "jazz" in (r.get("description") or "").lower()]
    if not todo or not os.environ.get("ANTHROPIC_API_KEY"):
        return records
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    cache, fixed = {}, 0
    for r in todo:
        d = r["description"]
        if d not in cache:
            try:
                new = _rewrite(client, d, "jazz")
            except Exception as e:
                print(f"  repair error: {e}"); new = ""
            cache[d] = new if (new and not _check(new)) else ""
        if cache[d]:
            r["description"] = cache[d]; fixed += 1
    print(f"  Repaired jazz wording in {fixed}/{len(todo)} blurbs")
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


def _extra(r):
    parts = []
    for k, lab in (("event_title", "Event title"), ("supporting_acts", "Supporting acts"), ("band_format", "Format"),
                   ("stage", "Stage"), ("special_occasion", "Occasion"), ("start_time", "Start")):
        if r.get(k):
            parts.append(f"{lab}: {r[k]}")
    return "\n".join(parts)


def run():
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if not os.environ.get("ANTHROPIC_API_KEY", ""):
        print("  ANTHROPIC_API_KEY not set - skipping")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    records = _apply_overrides(_tidy(load("gigs")))
    records = _repair_jazz(records, today)
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
                      first[a].get("special_occasion", ""), _extra(first[a])): a for a in artists}
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
            listing = d.startswith("\x00")
            r["description"] = d.lstrip("\x00")
            r["description_verified"] = False
            r["description_source"] = "listing" if listing else "auto"
            count += 1
    save("gigs", records)
    got = sum(1 for v in results.values() if v)
    print(f"  of which listing-derived: {sum(1 for v in results.values() if v.startswith(chr(0)))}")
    print(f"  Artists done {len(results)}/{len(artists)}, described {got}; gigs updated {count}; {int(time.time()-start)}s")
    future2 = [r for r in records if r.get("date", "") >= today]
    have2 = [r for r in future2 if r.get("description", "").strip()]
    print(f"  Final coverage: {len(have2)}/{len(future2)} ({100*len(have2)//max(len(future2),1)}%)")


if __name__ == "__main__":
    run()
