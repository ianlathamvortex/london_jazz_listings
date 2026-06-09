"""
enricher.py — Claude API description generator with web search
Uses real web search to find artist credentials before writing descriptions.
Never invents facts — leaves blank if nothing specific found.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from utils import load, save

MODEL       = "claude-sonnet-4-6"
MAX_TOKENS  = 300
MAX_PER_RUN = 20  # Lower limit — quality over quantity

SYSTEM_PROMPT = """You write short jazz gig descriptions for a London listings website.

STRICT RULES:
1. Search the web for the artist FIRST. Find at least ONE specific real fact:
   - A named album on a real label
   - A specific famous collaborator they've worked with  
   - A country of origin or training background
   - A named award or prize
   - A specific genre or sound they're known for

2. Write 2 sentences max, under 55 words, using ONLY facts you actually found.

3. BANNED phrases and approaches:
   - "rarely does a..." / "make you forget your phone"
   - "one of London's most..." / "most compelling young..."
   - "before the world catches on" / "name-dropping in five years"
   - "rewards both first-timers and seasoned ears"
   - Any sentence that could apply to ANY jazz musician
   - Rhetorical questions
   - Starting with the artist's name

4. If you cannot find specific facts about this artist, respond with exactly: SKIP

5. Never say "jazz" — they already know it's a jazz site.

6. The goal: sound like a knowledgeable friend who's actually heard this person.

GOOD EXAMPLE (Camille Bertault):
"French vocalist who became a YouTube sensation with her scat improvisation over 
Coltrane's Giant Steps. Live she's electrifying — her voice an instrument of 
extraordinary range and wit."

BAD EXAMPLE (Matt Anderson):
"Rarely does a tenor saxophonist make you forget to check your phone."
→ REJECTED: generic, could apply to anyone, no real facts.
"""


def generate_description(artist, venue, date, special=""):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        
        prompt = f"Artist to research and describe: {artist}\nVenue: {venue}, London\nDate: {date}"
        if special:
            prompt += f"\nSpecial occasion: {special}"
        prompt += "\n\nSearch for this artist, find a specific real fact, then write the description. If you find nothing specific, respond with exactly: SKIP"

        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract text from response
        for block in msg.content:
            if hasattr(block, 'text'):
                text = block.text.strip()
                if text and text != "SKIP" and len(text) > 20:
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
            print(f"  Reached {MAX_PER_RUN} limit for this run")
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
        
        if desc and desc.upper() != "SKIP":
            records[i]["description"] = desc
            count += 1
            changed = True
            print(f"  ✓ {artist[:40]}: {desc[:60]}...")
        else:
            print(f"  → Skipped (no specific facts found)")

    if changed:
        save("gigs", records)
        print(f"\n  Generated {count} new descriptions")
    else:
        print("  No new descriptions generated")


if __name__ == "__main__":
    run()
