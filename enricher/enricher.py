"""
enricher.py — Claude API description generator with web search
Runs nightly. Generates descriptions with a capped number of API attempts per run.
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
MAX_PER_RUN = 100
MAX_ATTEMPTS = 80  # cap API calls so a run can't hit the workflow timeout

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


def run():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — skipping")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    records = load("gigs")
    future = [r for r in records if r.get("date","") >= today]
    no_desc = [r for r in future if not r.get("description","").strip()]
    total = len(future)
    coverage_pct = int(100 * (total - len(no_desc)) / max(total, 1))

    print(f"Description coverage: {total - len(no_desc)}/{total} ({coverage_pct}%)")
    if coverage_pct < 50:
        print(f"  WARNING: COVERAGE BELOW 50% - {len(no_desc)} gigs need descriptions")

    count = 0
    attempts = 0
    changed = False
    for i, record in enumerate(records):
        if count >= MAX_PER_RUN or attempts >= MAX_ATTEMPTS:
            print(f"  Reached run limit (descriptions={count}, attempts={attempts})")
            break
        if record.get("description", "").strip():
            continue
        if record.get("date","") < today:
            continue
        artist  = record.get("artist_name", "")
        venue   = record.get("venue_name", "")
        date    = record.get("date", "")
        special = record.get("special_occasion", "")
        if not artist or not venue:
            continue

        print(f"  Researching: {artist[:45]}...")
        attempts += 1
        desc = generate_description(artist, venue, date, special)
        if desc:
            records[i]["description"] = desc
            records[i]["description_verified"] = False
            records[i]["description_source"] = "auto"
            count += 1
            changed = True
            print(f"  OK {artist[:40]}")
        else:
            print(f"  -> Skipped")

    if changed:
        save("gigs", records)
        print(f"  Generated {count} new descriptions")
    else:
        print("  No new descriptions generated")

    # Final coverage report
    records2 = load("gigs")
    future2 = [r for r in records2 if r.get("date","") >= today]
    no_desc2 = [r for r in future2 if not r.get("description","").strip()]
    print(f"  Final coverage: {len(future2)-len(no_desc2)}/{len(future2)} ({int(100*(len(future2)-len(no_desc2))/max(len(future2),1))}%)")


if __name__ == "__main__":
    run()
