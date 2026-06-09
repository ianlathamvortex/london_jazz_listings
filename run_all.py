"""
run_all.py — Master runner: executes all scrapers then enricher
"""
import sys
import traceback
import importlib
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scrapers"))
sys.path.insert(0, str(ROOT / "enricher"))

from utils import FILES, load, save
for category, path in FILES.items():
    if not path.exists():
        save(category, [])

print(f"\n{'='*60}")
print(f"London Jazz Scrapers — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}\n")

SCRAPERS = [
    ("Ronnie Scott's",       "scraper_ronnies"),
    ("606 Club",             "scraper_606"),
    ("Vortex",               "scraper_vortex"),
    ("PizzaExpress Jazz",    "scraper_pizzaexpress"),
    ("MusicGlue venues",     "scraper_musicglue"),
    ("Serious Promotions",   "scraper_serious"),
    ("Smaller venues",       "scraper_venues"),
    ("UK Jazz News",         "scraper_ukjazznews"),
    ("Trinity Laban",        "scraper_trinitylaban"),
    ("Jazzlive at The Crypt","scraper_jazzlive"),
    ("Lauderdale House",     "scraper_lauderdale"),
    ("World Heart Beat",    "scraper_worldheartbeat"),
    ("Highams Park Jazz",   "scraper_highamsparkjazz"),
    ("Wigmore Hall",        "scraper_wigmorehall"),
    ("Cadogan Hall",       "scraper_cadogan"),
    ("Café OTO",             "scraper_cafeoto"),
    ("King's Place",         "scraper_kingsplace"),
]

results = {}
for name, module_name in SCRAPERS:
    print(f"\n── {name} ──")
    try:
        mod = importlib.import_module(module_name)
        mod.run()
        results[name] = "✓ OK"
    except Exception as e:
        print(f"  ERROR: {e}")
        traceback.print_exc()
        results[name] = f"✗ FAILED: {e}"

print(f"\n── Claude API Enricher ──")
try:
    import enricher
    enricher.run()
    results["Enricher"] = "✓ OK"
except Exception as e:
    print(f"  ERROR: {e}")
    results["Enricher"] = f"✗ FAILED: {e}"

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
for name, status in results.items():
    print(f"  {status:20} {name}")

print(f"\nDATA FILES")
for category, path in FILES.items():
    records = load(category)
    future = [r for r in records
              if r.get("date","") >= datetime.now().strftime("%Y-%m-%d")]
    print(f"  {category:20} {len(future):4} future / {len(records):4} total")

print(f"\nDone — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
