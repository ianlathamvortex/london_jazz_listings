"""
run_all.py — Master runner: executes all scrapers then enricher
Run locally: python run_all.py
Run in CI:   triggered by GitHub Actions nightly
"""
import sys
import traceback
from pathlib import Path
from datetime import datetime

# Add scrapers directory to path
sys.path.insert(0, str(Path(__file__).parent / "scrapers"))
sys.path.insert(0, str(Path(__file__).parent / "enricher"))

# Initialise empty data files if they don't exist
from scrapers.utils import FILES, load, save
for category, path in FILES.items():
    if not path.exists():
        save(category, [])
        print(f"Initialised {path.name}")

print(f"\n{'='*60}")
print(f"London Jazz Scrapers — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}\n")

# ── Scrapers ──────────────────────────────────────────────────────────────
SCRAPERS = [
    ("Ronnie Scott's",      "scrapers.scraper_ronnies",     "run"),
    ("606 Club",            "scrapers.scraper_606",         "run"),
    ("Vortex",              "scrapers.scraper_vortex",      "run"),
    ("PizzaExpress Jazz",   "scrapers.scraper_pizzaexpress","run"),
    ("MusicGlue (Karamel)", "scrapers.scraper_musicglue",   "run"),
    ("Serious Promotions",  "scrapers.scraper_serious",     "run"),
    ("Smaller venues",      "scrapers.scraper_venues",      "run"),
    ("UK Jazz News",        "scrapers.scraper_ukjazznews",  "run"),
]

results = {}
for name, module_path, func in SCRAPERS:
    print(f"\n── {name} ──")
    try:
        import importlib
        mod = importlib.import_module(module_path)
        getattr(mod, func)()
        results[name] = "✓ OK"
    except Exception as e:
        print(f"  ERROR: {e}")
        traceback.print_exc()
        results[name] = f"✗ FAILED: {e}"

# ── Enricher ──────────────────────────────────────────────────────────────
print(f"\n── Claude API Enricher ──")
try:
    from enricher.enricher import run as enrich_run
    enrich_run()
    results["Enricher"] = "✓ OK"
except Exception as e:
    print(f"  ERROR: {e}")
    results["Enricher"] = f"✗ FAILED: {e}"

# ── Summary ───────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
for name, status in results.items():
    print(f"  {status:20} {name}")

# Print record counts
print(f"\nDATA FILES")
for category, path in FILES.items():
    records = load(category)
    future = [r for r in records
              if r.get("date","") >= datetime.now().strftime("%Y-%m-%d")]
    print(f"  {category:20} {len(future):4} future / {len(records):4} total")

print(f"\nDone — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
