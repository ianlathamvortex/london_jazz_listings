"""
enricher.py — Claude API description generator
Generates "why you should go" descriptions for new gigs.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from utils import load, save

MODEL      = "claude-sonnet-4-20250514"
MAX_TOKENS = 120
MAX_PER_RUN = 50

SYSTEM_PROMPT = """You write short, punchy jazz gig descriptions for a London listings website.
Your tone: knowledgeable but never stuffy. Like a recommendation from a well-informed friend.
Each description must:
- Explain WHY the gig is worth seeing (not just who's playing)
- Include one credential or context that lands with a non-specialist
- Be 2 sentences maximum, under 60 words
- Never use the word "jazz" (they already know it's a jazz site)
- Never start with the artist's name
Do not add any preamble, labels or quotation marks. Just the description text."""


def generate_description(artist, venue, date, extra=""):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        prompt = f"Artist: {artist}\nVenue: {venue}\nDate: {date}\n"
        if extra:
            prompt += f"Context: {extra}\n"
        prompt += "\nWrite the description:"
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except KeyError:
        print("  ANTHROPIC_API_KEY not set — skipping enrichment")
        return ""
    except Exception as e:
        print(f"  API error for {artist}: {e}")
        return ""


def run():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — skipping enrichment")
        print("  (Add key to GitHub secrets to enable AI descriptions)")
        return

    print("Enriching gigs...")
    records = load("gigs")
    count = 0
    changed = False

    for i, record in enumerate(records):
        if count >= MAX_PER_RUN:
            break
        if record.get("description", "").strip():
            continue
        artist  = record.get("artist_name", "")
        venue   = record.get("venue_name", "")
        date    = record.get("date", "")
        special = record.get("special_occasion", "")
        if not artist or not venue:
            continue
        desc = generate_description(artist, venue, date, special)
        if desc:
            records[i]["description"] = desc
            count += 1
            changed = True
            print(f"  ✓ {artist} @ {venue}")

    if changed:
        save("gigs", records)
        print(f"  Generated {count} new descriptions")
    else:
        print("  No new descriptions needed")


if __name__ == "__main__":
    run()
