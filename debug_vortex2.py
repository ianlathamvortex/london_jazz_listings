import sys
sys.path.insert(0, "scrapers")
from scraper_vortex import _scrape_day

out = []
test_dates = ["2026-07-23", "2026-07-10", "2026-08-26", "2026-07-13"]
for d in test_dates:
    url = f"https://www.vortexjazz.co.uk/events/{d}/"
    gigs = _scrape_day(url, d)
    out.append(f"{d}: {len(gigs)} gig(s)")
    for g in gigs:
        out.append(f"  {g['artist_name']!r} | price={g['price_from']} | ticket={g['ticket_url']}")

open("debug_output6.txt", "w").write("\n".join(out))
print("\n".join(out))
