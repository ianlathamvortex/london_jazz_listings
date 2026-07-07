import sys, json
sys.path.insert(0, "scrapers")
from scraper_jazzlive import scrape

results = scrape()
out = [f"Total gigs found: {len(results)}"]
for g in results:
    out.append(f"{g['date']} | {g['artist_name']} | price={g['price_from']} | special={g['special_occasion']!r} | ticket={g['ticket_url']}")
    out.append(f"  desc: {g['description'][:150]}")

open("debug_output4.txt", "w").write("\n".join(out))
print("\n".join(out))
