"""
enricher.py — Claude API description generator with web search
Generates factual gig descriptions. Flags all auto-generated as unverified.
Never invents facts — skips if nothing specific found.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from utils import load, save

MODEL       = "claude-sonnet-4-6"
MAX_TOKENS  = 150
MAX_PER_RUN = 20

# If any of these appear in the output, discard it — model exposed its reasoning
BAD_PATTERNS = [
    "no relevant results", "no specific", "couldn't find", "could not find",
    "i couldn't", "i could not", "unfortunately", "let me try",
    "more targeted search", "based on my search", "my search revealed",
    "i found no", "i was unable", "unable to find", "i searched",
    "here is the listing description", "here\'s the description",
    "after searching", "i\'ve searched", "search results",
]

SYSTEM_PROMPT = """You write short jazz gig descriptions for a London listings website.

PROCESS:
1. Search the web for the artist
2. Find ONE specific verifiable fact: named album + label, specific famous collaborator, award, country of origin, or training background
3. Write exactly 2 sentences, under 55 words, using ONLY facts you found

CRITICAL RULES:
- If you cannot find specific facts, respond with exactly the word: SKIP
- Never write about your search process — just the description or SKIP
- Never say "jazz" (they know it\'s a jazz site)
- Never start with the artist name
- Banned phrases: "rarely does", "make you forget", "most compelling young", "before the world catches on", "seasoned ears", any generic praise
- No preamble, no "Here is the description:", no explanation — just the text or SKIP

GOOD EXAMPLE (Camille Bertault):
French vocalist who became a YouTube sensation with her scat improvisation over Coltrane\'s Giant Steps. Live she\'s electrifying — her voice an instrument of extraordinary range and wit.

BAD — respond SKIP instead:
- "No relevant results found for X"
- "I couldn\'t find specific facts about Y"
- Any sentence about your search process"""


def _is_bad_description(text: str) -> bool:
    """Return True if the text is model reasoning leaked into output."""
    t = text.lower()
    return any(p in t for p in BAD_PATTERNS)


def generate_description(artist: str, venue: str, date: str, special: str = "") -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        prompt = f"Artist: {artist}\nVenue: {venue}, London\nDate: {date}"
        if special:
            prompt += f"\nOccasion: {special}"
        prompt += "\n\nWrite the description or SKIP:"

        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text blocks only
        for block in msg.content:
            if hasattr(block, "text"):
                text = block.text.strip()
                if not text:
                    continue
                if text.upper() == "SKIP":
                    return ""
                if _is_bad_description(text):
                    return ""  # silently discard — never expose to users
                if len(text) > 20:
                    return text

        return ""

    except KeyError:
        print("  ANTHROPIC_API_KEY not set")
        return ""
    except Exception as e:
        print(f"  API error for {artist}: {e}")
        return ""


def run():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — skipping enrichment")
        return

    print(f"Enriching gigs with web search (model: {MODEL})...")
    records = load("gigs")
    count = 0
    changed = False

    for i, record in enumerate(records):
        if count >= MAX_PER_RUN:
            print(f"  Reached {MAX_PER_RUN} limit")
            break
        if record.get("description", "").strip():
            continue

        artist  = record.get("artist_name", "")
        venue   = record.get("venue_name", "")
        date    = record.get("date", "")
        special = record.get("special_occasion", "")

        if not artist or not venue:
            continue

        print(f"  Researching: {artist[:45]}...")
        desc = generate_description(artist, venue, date, special)

        if desc:
            records[i]["description"] = desc
            records[i]["description_verified"] = False
            records[i]["description_source"] = "auto"
            count += 1
            changed = True
            print(f"  ✓ {artist[:40]}")
        else:
            print(f"  → Skipped")

    if changed:
        save("gigs", records)
        print(f"  Generated {count} new descriptions")
    else:
        print("  No new descriptions generated")


if __name__ == "__main__":
    run()
