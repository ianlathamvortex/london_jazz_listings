"""
enricher.py — Claude API description generator with web search
Uses real web search to find artist credentials before writing.
Flags all auto-generated descriptions as unverified for editorial review.
Never invents facts — skips if nothing specific found.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from utils import load, save

MODEL       = "claude-sonnet-4-6"
MAX_TOKENS  = 300
MAX_PER_RUN = 20

SYSTEM_PROMPT = """You write short jazz gig descriptions for a London listings website.

PROCESS:
1. Search the web for the artist name + "jazz" or "musician"
2. Find at least ONE specific verifiable fact:
   - Named album on a real label (e.g. "debut album 'X' on ECM")
   - Specific famous collaborator (e.g. "played with Shabaka Hutchings")
   - Country of origin or training (e.g. "New York-born", "Guildhall-trained")
   - Named award or publication credit (e.g. "Mercury Prize nominated", "praised by DownBeat")
   - Specific genre or lineage (e.g. "rooted in the Ornette Coleman tradition")
3. Write 2 sentences max, under 55 words, using ONLY facts you found
4. If you find nothing specific and verifiable, respond with exactly: SKIP

BANNED — any of these means automatic rejection:
- "rarely does a..."
- "make you forget your phone"
- "one of London's most compelling..."
- "before the rest of the world catches on"
- "rewards both first-timers and seasoned ears"
- "name-dropping in five years"
- "rare authority" — reserved only for confirmed masters (e.g. Kamasi Washington, Iain Ballamy). Do not use for anyone else.
- "rare talent", "rare gift", "rare ability" — same rule
- "captivating presence", "compelling performer", "extraordinary talent" — banned entirely, generic
- "virtuoso" — reserved for musicians who genuinely redefine what is possible (Art Tatum, Jacob Collier level). Never use for a working jazz musician regardless of their own bio or press material.
- Any sentence that could apply to ANY musician
- Invented nationality or instrument
- ECM aesthetic unless you found a real ECM connection
- Never start with the artist name
- Never mention the artist name anywhere in the description — it is already in the title. This includes possessives ("X's quartet") and pronouns that only make sense if you've stated the name.
- Never mention the venue in the description — it is shown separately on the listing
- Never state "album launch" or "launching their new album" in the description — this is tagged separately and is not a reliable quality signal
- Never say "jazz"
- "rare chance to catch", "rare chance to hear", "rare opportunity" — banned unless the artist genuinely plays London once a year or less (e.g. international star, one-off reunion). A London-based musician who gigs regularly is never a "rare chance".

GOOD (Camille Bertault):
"French vocalist who became a YouTube sensation with her scat improvisation over 
Coltrane's Giant Steps. Live she's electrifying — her voice an instrument of 
extraordinary range and wit."
→ APPROVED: specific real fact, specific sound, nothing invented

BAD (Matt Anderson):
"Rarely does a tenor saxophonist make you forget to check your phone."
→ REJECTED: no facts, generic, could apply to anyone

If unsure, SKIP. A blank description is better than a wrong one."""


def generate_description(artist, venue, date, special=""):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        prompt = f"Artist: {artist}\nVenue: {venue}, London\nDate: {date}"
        if special:
            prompt += f"\nSpecial occasion: {special}"
        prompt += "\n\nSearch for this artist, find one specific real fact, then write the description. If nothing specific found, respond: SKIP"

        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        for block in msg.content:
            if hasattr(block, 'text'):
                text = block.text.strip()
                if text.upper() == "SKIP" or not text:
                    return ""
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

        # Skip if already has a verified description
        if record.get("description", "").strip() and record.get("description_verified"):
            continue

        # Skip if already has a description (verified or manual — don't overwrite)
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
            records[i]["description_verified"] = False  # Needs editorial review
            records[i]["description_source"] = "auto"
            count += 1
            changed = True
            print(f"  ✓ {artist[:40]} [UNVERIFIED]")
        else:
            print(f"  → Skipped")

    if changed:
        save("gigs", records)
        print(f"\n  Generated {count} new descriptions (all marked unverified)")
    else:
        print("  No new descriptions generated")


if __name__ == "__main__":
    run()
