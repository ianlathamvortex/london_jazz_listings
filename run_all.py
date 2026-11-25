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

# IMPORTANT: Only initialise missing data files — never overwrite existing ones
for category, path in FILES.items():
    if not path.exists():
        print(f"  WARNING: {path} missing — creating empty file")
        save(category, [])

print(f"\n{'='*60}")
print(f"London Jazz Scrapers — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}\n")

# Safety check — abort if gigs.json is empty (means something went wrong)
gigs = load("gigs")
if len(gigs) == 0:
    print("WARNING: gigs.json is empty before scraping — possible data loss risk")
    print("Scrapers will run but will not save if result is also empty")

# (name, module, cadence): "daily" | "weekly" (Sundays) | "monthly" (1st of month).
# Manual runs (workflow_dispatch) or RUN_ALL=1 always run everything.
SCRAPERS = [
    ("Ronnie Scott's", "scraper_ronnies", "weekly"),
    ("606 Club", "scraper_606", "weekly"),
    ("Vortex", "scraper_vortex", "weekly"),
    ("PizzaExpress Jazz", "scraper_pizzaexpress", "weekly"),
    ("MusicGlue venues", "scraper_musicglue", "weekly"),
    ("Serious Promotions", "scraper_serious", "monthly"),
    ("Smaller venues", "scraper_venues", "weekly"),
    ("UK Jazz News", "scraper_ukjazznews", "weekly"),
    ("Jazzlive at The Crypt", "scraper_jazzlive", "weekly"),
    ("Lauderdale House", "scraper_lauderdale", "weekly"),
    ("World Heart Beat", "scraper_worldheartbeat", "weekly"),
    ("Highams Park Jazz", "scraper_highamsparkjazz", "weekly"),
    ("Trinity Laban", "scraper_trinitylaban", "monthly"),
    ("Guildhall (GSMD)", "scraper_gsmd", "monthly"),
    ("Wigmore Hall", "scraper_wigmorehall", "monthly"),
    ("Cadogan Hall", "scraper_cadogan", "monthly"),
    ("Cafe OTO", "scraper_cafeoto", "monthly"),
    ("Kings Place", "scraper_kingsplace", "monthly"),
]

import os
_now = datetime.now()
_force = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or os.environ.get("RUN_ALL") == "1"

def due(cadence):
    if _force or cadence == "daily":
        return True
    if cadence == "weekly":
        return _now.weekday() == 6
    if cadence == "monthly":
        return _now.day == 1
    return True

results = {}
for name, module_name, cadence in SCRAPERS:
    if not due(cadence):
        results[name] = f"- not due ({cadence})"
        continue
    print(f"\n── {name} ──")
    try:
        mod = importlib.import_module(module_name)
        mod.run()
        results[name] = "✓ OK"
    except ModuleNotFoundError:
        print(f"  SKIP: {module_name} not found")
        results[name] = "⊘ SKIPPED"
    except Exception as e:
        print(f"  ERROR: {e}")
        traceback.print_exc()
        results[name] = f"✗ FAILED: {e}"

# Safety check — abort commit if gigs result is suspiciously small
final_gigs = load("gigs")
if len(final_gigs) < 50:
    print(f"\nWARNING: Only {len(final_gigs)} gigs after scraping — suspiciously low")
    print("This may indicate a scraper failure. Check logs before committing.")

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
