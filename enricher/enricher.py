"""
enricher.py — Claude API description generator
Generates "why you should go" descriptions for new gigs.
Skips gigs that already have a description.

TO ACTIVATE: ensure ANTHROPIC_API_KEY is set in environment / GitHub secrets.
"""
import os
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from utils import load, save

# ── CONFIG ────────────────────────────────────────────────────────────────
MODEL          = "claude-sonnet-4-20250514"
MAX_TOKENS     = 120
MAX_PER_RUN    = 50   # cap API calls per nightly run
CATEGORIES     = ["gigs"]  # extend to other categories if needed

SYSTEM_PROMPT = """You write short, punchy jazz gig descriptions for a London listings website.
Your tone: knowledgeable but never stuffy. Like a recommendation from a well-informed friend.
Each description must:
- Explain WHY the gig is worth seeing (not just who's playing)
- Include one credential or context that lands with a non-specialist
- Be 2 sentences maximum, under 60 words
- Never use the word "jazz" (they already know it's a jazz site)
- Never start with the artist's name
Do not add any preamble, labels or quotation marks. Just the description text."""


def generate_description(artist: str, venue: str, date: str,
                          existing_info: str = "") -> str:
    """Call Claude API to generate a gig description."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        user_prompt = (
            f"Artist: {artist}\n"
            f"Venue: {venue}\n"
            f"Date: {date}\n"
        )
        if existing_info:
            user_prompt += f"Additional context: {existing_info}\n"
        user_prompt += "\nWrite the description:"

        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return message.content[0].text.strip()

    except ImportError:
        print("  WARNING: anthropic package not installed")
        return ""
    except KeyError:
        print("  WARNING: ANTHROPIC_API_KEY not set — skipping enrichment")
        return ""
    except Exception as e:
        print(f"  WARNING: API error for {artist}: {e}")
        return ""


def enrich(category: str = "gigs"):
    """Add descriptions to any gigs that don't have one."""
    print(f"Enriching {category}...")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — skipping enrichment")
        print("  (Add key to GitHub secrets to enable AI descriptions)")
        return

    records = load(category)
    enriched_count = 0
    changed = False

    for i, record in enumerate(records):
        if enriched_count >= MAX_PER_RUN:
            print(f"  Reached {MAX_PER_RUN} descriptions per run limit")
            break

        # Skip if already has a description
        if record.get("description", "").strip():
            continue

        artist  = record.get("artist_name", "")
        venue   = record.get("venue_name", "")
        date    = record.get("date", "")
        special = record.get("special_occasion", "")

        if not artist or not venue:
            continue

        extra = ""
        if special:
            extra = f"Special occasion: {special}"

        desc = generate_description(artist, venue, date, extra)
        if desc:
            records[i]["description"] = desc
            enriched_count += 1
            changed = True
            print(f"  ✓ {artist} @ {venue}")

    if changed:
        save(category, records)
        print(f"  Generated {enriched_count} new descriptions")
    else:
        print(f"  No new descriptions needed")


def run():
    for category in CATEGORIES:
        enrich(category)


if __name__ == "__main__":
    run()
