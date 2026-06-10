"""
link_validator.py — Check all ticket_url fields in gigs.json (and other data files)
Sets link_dead=True for URLs returning 4xx/5xx or timing out.
Clears link_dead=False for URLs that recover.
Run as part of the nightly pipeline after scrapers, before commit.
"""

import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

DATA_DIR = Path(__file__).parent.parent / "data"

# ── Domains whose root homepage is always live — skip homepage-only URLs ──────
# These are major venue/ticketing sites; a homepage-only URL is intentional fallback
ALWAYS_LIVE_DOMAINS = {
    "vortexjazz.co.uk",
    "cadoganhall.com",
    "ronniescotts.co.uk",
    "brasseriezedel.com",
    "wigmore-hall.org.uk",
    "barbican.org.uk",
    "southbankcentre.co.uk",
    "royalalberthall.com",
    "kingsplace.co.uk",
    "serious.org.uk",
    "606club.co.uk",
    "lauderdalehouse.co.uk",
    "jazzlive.co.uk",
    "worldheartbeat.org",
}

# ── Domains that frequently redirect or require JS — skip 4xx false positives ─
SKIP_VALIDATION_DOMAINS = {
    "dice.fm",           # bot detection
    "eventbrite.co.uk",  # often 403 to scripts
    "ticketmaster.co.uk",
    "instagram.com",
    "facebook.com",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-GB,en;q=0.9",
}

TIMEOUT = 10  # seconds
DELAY   = 0.3 # seconds between requests (be polite)


def _domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def _is_homepage_only(url: str) -> bool:
    path = urlparse(url).path.rstrip("/")
    return not path or path == ""


def should_skip(url: str) -> tuple[bool, str]:
    """Return (skip, reason)."""
    if not url:
        return True, "blank"
    dom = _domain(url)
    if dom in SKIP_VALIDATION_DOMAINS:
        return True, f"skip-domain ({dom})"
    if _is_homepage_only(url) and dom in ALWAYS_LIVE_DOMAINS:
        return True, "homepage-only major venue"
    return False, ""


def check_url(url: str) -> tuple[bool, int | None, str]:
    """
    Returns (is_alive, status_code, reason).
    is_alive=True means the link is usable.
    """
    req = urllib.request.Request(url, headers=HEADERS, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            code = resp.status
            if code < 400:
                return True, code, "ok"
            return False, code, f"HTTP {code}"
    except urllib.error.HTTPError as e:
        # Some servers reject HEAD but accept GET — retry with GET for 405
        if e.code == 405:
            try:
                req_get = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req_get, timeout=TIMEOUT) as resp:
                    return True, resp.status, "ok (GET fallback)"
            except Exception:
                pass
        # 403/405 from a real page often means the page exists but rejects bots
        # Don't mark as dead — mark as unverified
        if e.code in (403, 405, 429):
            return True, e.code, f"HTTP {e.code} (unverified — page may exist)"
        return False, e.code, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, None, f"URLError: {e.reason}"
    except Exception as e:
        return False, None, f"Error: {e}"


def validate_file(filename: str) -> dict:
    """Validate all ticket/booking URLs in a JSON data file. Returns stats."""
    path = DATA_DIR / filename
    if not path.exists():
        return {}

    with open(path) as f:
        records = json.load(f)

    today = datetime.now().strftime("%Y-%m-%d")

    # URL fields to check per file type
    url_fields = {
        "gigs.json":        ["ticket_url"],
        "free_entry.json":  ["booking_url", "source_url"],
        "jam_sessions.json":["website"],
        "brunches.json":    ["ticket_url", "booking_url"],
        "festivals.json":   ["ticket_url"],
    }
    fields = url_fields.get(filename, ["ticket_url"])

    stats = {"checked": 0, "dead": 0, "recovered": 0, "skipped": 0, "newly_dead": []}
    changed = False

    for record in records:
        # Skip past events
        date = record.get("date", "")
        if date and date < today:
            continue

        for field in fields:
            url = record.get(field, "")
            if not url:
                continue

            skip, skip_reason = should_skip(url)
            if skip:
                stats["skipped"] += 1
                continue

            stats["checked"] += 1
            was_dead = record.get("link_dead", False)

            alive, code, reason = check_url(url)
            time.sleep(DELAY)

            if alive:
                if was_dead:
                    record["link_dead"] = False
                    record["link_dead_reason"] = ""
                    stats["recovered"] += 1
                    changed = True
                    print(f"  ✓ RECOVERED  {url[:70]}")
                # else: fine, no change
            else:
                record["link_dead"] = True
                record["link_dead_reason"] = reason
                stats["dead"] += 1
                changed = True
                artist = record.get("artist_name") or record.get("session_name") or record.get("event_name", "?")
                stats["newly_dead"].append({
                    "artist": artist,
                    "url": url,
                    "reason": reason,
                })
                marker = "NEW " if not was_dead else "    "
                print(f"  ✗ {marker}DEAD  {artist[:35]:35}  {reason:20}  {url[:50]}")

    if changed:
        with open(path, "w") as f:
            json.dump(records, f, indent=2, default=str)
        print(f"  Saved {path.name} (link_dead flags updated)")

    return stats


def run():
    print(f"\n── Link Validator ──")
    print(f"Checking ticket URLs across all data files...")

    all_dead = []
    total_checked = total_dead = total_skipped = total_recovered = 0

    for filename in ["gigs.json", "free_entry.json", "jam_sessions.json", "brunches.json", "festivals.json"]:
        path = DATA_DIR / filename
        if not path.exists():
            continue
        print(f"\n  {filename}")
        stats = validate_file(filename)
        total_checked   += stats.get("checked", 0)
        total_dead      += stats.get("dead", 0)
        total_skipped   += stats.get("skipped", 0)
        total_recovered += stats.get("recovered", 0)
        all_dead.extend(stats.get("newly_dead", []))

    print(f"\n  Checked: {total_checked}  Dead: {total_dead}  "
          f"Recovered: {total_recovered}  Skipped: {total_skipped}")

    if all_dead:
        print(f"\n  ⚠  {len(all_dead)} dead link(s) need attention:")
        for item in all_dead:
            print(f"     {item['artist'][:40]:40}  {item['url'][:60]}")

    return {"dead": total_dead, "checked": total_checked}


if __name__ == "__main__":
    run()
