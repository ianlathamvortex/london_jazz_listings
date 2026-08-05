import sys
sys.path.insert(0, "scrapers")
from scraper_jazzvespers import scrape

results = scrape()
out = [f"Total gigs found: {len(results)}"]
for g in results:
    out.append(f"{g['date']} {g['start_time']} | {g['artist_name']} | {g['ticket_url']}")
    out.append(f"  desc: {g['description'][:150]}")

open("debug_output_vespers.txt", "w").write("\n".join(out))
print("\n".join(out))
