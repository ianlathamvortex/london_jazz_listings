import sys
sys.path.insert(0, "scrapers")
from scraper_606 import scrape

results = scrape()
out = [f"Total gigs found: {len(results)}"]
for g in results:
    out.append(f"{g['date']} {g['start_time']} | {g['artist_name']} | price={g['price_from']}")

open("debug_output_606c.txt", "w").write("\n".join(out))
print("\n".join(out))
