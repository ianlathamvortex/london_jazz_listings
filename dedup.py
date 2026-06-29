#!/usr/bin/env python3
"""
dedup.py — remove duplicate gigs from gigs.json
Runs nightly after scrapers. Catches duplicates introduced by:
- Multiple scrapers picking up the same gig
- Manual additions that duplicate scraped entries
- Scraper reruns adding already-present gigs

Duplicates = same date + venue + normalised artist name.
Early/Late Show parentheticals are preserved (not stripped) so
two-show nights are kept as separate entries.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).parent


def normalise(name: str) -> str:
    """Normalise artist name for comparison — strip band format suffixes only."""
    n = name.lower().strip()
    # Strip band format suffixes (Quartet, Trio etc) but NOT show descriptors
    n = re.sub(
        r'\s+(quartet|trio|duo|quintet|sextet|septet|octet|'
        r'big band|orchestra|ensemble|project|group|band|collective)$',
        '', n
    )
    return n.strip()


def dedup(gigs: list) -> tuple[list, int]:
    seen = {}   # (date, venue, norm_name) → index of best entry
    removed = set()

    for i, g in enumerate(gigs):
        if g.get("hidden"):
            continue
        key = (
            g.get("date", ""),
            g.get("venue_name", ""),
            normalise(g.get("artist_name", "")),
        )
        if key in seen:
            j = seen[key]
            canonical = gigs[j]
            # Score each entry — keep the one with more editorial data
            def score(x):
                return (
                    len(x.get("description", "") or "") +
                    (20 if x.get("editors_pick") else 0) +
                    (10 if x.get("description_verified") else 0) +
                    (5 if x.get("description_source") == "manual" else 0) +
                    (3 if x.get("price_from") else 0) +
                    (2 if x.get("ticket_url") else 0)
                )
            if score(g) > score(canonical):
                removed.add(j)
                seen[key] = i
            else:
                removed.add(i)
            winner = gigs[seen[key]]
            loser = gigs[list({j, i} - {seen[key]})[0]]
            print(f"  DUP removed: '{loser['artist_name']}' "
                  f"(kept: '{winner['artist_name']}') "
                  f"on {g['date']} @ {g.get('venue_name', '')}")
        else:
            seen[key] = i

    clean = [g for i, g in enumerate(gigs) if i not in removed]
    return clean, len(removed)


def main():
    path = ROOT / "gigs.json"
    with open(path) as f:
        gigs = json.load(f)

    before = len(gigs)
    clean, n_removed = dedup(gigs)

    if n_removed:
        with open(path, "w") as f:
            json.dump(clean, f, indent=2)
        print(f"dedup: removed {n_removed} duplicates ({before} → {len(clean)})")
    else:
        print(f"dedup: no duplicates found ({before} gigs)")


if __name__ == "__main__":
    main()
