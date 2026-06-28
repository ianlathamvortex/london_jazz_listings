#!/usr/bin/env python3
"""
coverage_check.py — nightly venue coverage checker
Runs after scrapers to flag gaps in core nightly venues.
Writes coverage_report.md to repo root.
Exits with code 1 if critical gaps found (triggers workflow warning).
"""
import json, sys
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent

# Core nightly venues — expected nights per week
CORE_VENUES = {
    "Ronnie Scott's":         {"min_per_week": 5, "scraper": "scraper_ronnies.py"},
    "606 Jazz Club":          {"min_per_week": 5, "scraper": "scraper_606.py"},
    "Vortex Jazz Club":       {"min_per_week": 4, "scraper": "scraper_vortex.py"},
    "PizzaExpress Jazz Club": {"min_per_week": 3, "scraper": "scraper_pizzaexpress.py"},
}

# Check window — next 14 days (reasonable horizon for all scrapers)
TODAY = date.today()
WINDOW = 14


def load_gigs():
    with open(ROOT / "gigs.json") as f:
        return json.load(f)


def check_coverage(gigs: list) -> dict:
    # Build venue → dates lookup
    venue_dates = defaultdict(set)
    for g in gigs:
        if g.get("hidden"):
            continue
        try:
            d = date.fromisoformat(g["date"])
        except:
            continue
        if TODAY <= d <= TODAY + timedelta(days=WINDOW):
            vname = g.get("venue_name", "")
            for cv in CORE_VENUES:
                if cv.lower() in vname.lower():
                    venue_dates[cv].add(d)

    results = {}
    for venue, config in CORE_VENUES.items():
        covered = venue_dates[venue]
        # Count weeks in window
        weeks = WINDOW / 7
        expected = int(config["min_per_week"] * weeks)
        actual = len(covered)

        # Find gaps — consecutive missing days
        gaps = []
        run = []
        for i in range(WINDOW + 1):
            d = TODAY + timedelta(days=i)
            if d not in covered:
                run.append(d)
            else:
                if run:
                    gaps.append(run)
                run = []
        if run:
            gaps.append(run)

        # Only flag runs of 3+ days as real gaps (shorter could be dark nights)
        real_gaps = [r for r in gaps if len(r) >= 3]

        results[venue] = {
            "actual": actual,
            "expected": expected,
            "pct": actual / max(expected, 1) * 100,
            "critical": actual < (expected * 0.5),  # below 50% = critical
            "gaps": real_gaps,
            "scraper": config["scraper"],
        }

    return results


def write_report(results: dict) -> str:
    today_str = TODAY.isoformat()
    lines = [
        f"# Coverage Report — {today_str}",
        f"Window: next {WINDOW} days\n",
    ]

    critical_venues = []
    for venue, r in results.items():
        status = "🔴 CRITICAL" if r["critical"] else ("🟡 LOW" if r["pct"] < 75 else "🟢 OK")
        lines.append(f"## {status} — {venue}")
        lines.append(f"- Coverage: {r['actual']}/{r['expected']} days ({r['pct']:.0f}%)")
        lines.append(f"- Scraper: `{r['scraper']}`")
        if r["gaps"]:
            lines.append("- Gaps (3+ days):")
            for gap in r["gaps"][:3]:
                start = gap[0].strftime("%a %d %b")
                end = gap[-1].strftime("%a %d %b")
                if len(gap) == 1:
                    lines.append(f"  - {start}")
                else:
                    lines.append(f"  - {start} – {end} ({len(gap)} days)")
        lines.append("")
        if r["critical"]:
            critical_venues.append(venue)

    if critical_venues:
        lines.append(f"⚠️ **Critical gaps: {', '.join(critical_venues)}**")

    return "\n".join(lines)


def main():
    gigs = load_gigs()
    results = check_coverage(gigs)
    report = write_report(results)

    # Write report
    report_path = ROOT / "coverage_report.md"
    report_path.write_text(report)
    print(report)

    # Exit code signals to workflow
    critical = any(r["critical"] for r in results.values())
    if critical:
        print("\n⚠️  CRITICAL GAPS FOUND — check coverage_report.md")
        sys.exit(1)
    else:
        print("\n✓ Coverage OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
