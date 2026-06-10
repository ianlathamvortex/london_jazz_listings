#!/usr/bin/env python3
"""
prerender.py — Static HTML pre-rendering for londonjazzlist.co.uk
Generates gig cards as real HTML inside gigs.html so Google can index
all artist names, venues and dates on first crawl (no JS required).

The JS init() still runs for interactivity — it replaces #listings with
the live-filtered version. But Google's first-pass crawler sees full content.

Run: python prerender.py
Updates: gigs.html in place
"""

import json
import re
import html as htmllib
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent


def esc(s: str) -> str:
    return htmllib.escape(str(s or ""), quote=True)


def load_gigs() -> list:
    with open(ROOT / "gigs.json") as f:
        gigs = json.load(f)
    today = date.today().isoformat()
    return [
        g for g in gigs
        if g.get("date", "") >= today
        and not g.get("hidden")
        and (g.get("price_from") or "").lower() != "free"
    ]


def gig_score(g: dict) -> int:
    PREMIUM_VENUES = {
        "Barbican Centre", "Cadogan Hall", "Royal Albert Hall",
        "Royal Festival Hall", "Wigmore Hall", "Union Chapel",
        "EartH Theatre", "Ronnie Scott's", "Ladbroke Hall",
    }
    SUB_ROOMS = {"Culford Room", "Elgar Room", "Upstairs at Ronnie's",
                 "Linbury Studio", "Purcell Room"}
    VENUE_CAPACITY = {
        "Barbican": 1900, "Barbican Centre": 1900,
        "Royal Albert Hall": 5272, "Royal Festival Hall": 2900,
        "Queen Elizabeth Hall": 900, "Cadogan Hall": 900,
        "Wigmore Hall": 540, "Union Chapel": 700, "EartH Theatre": 550,
        "King's Place": 420, "Ronnie Scott's": 240, "Lauderdale House": 200,
        "Jazz Cafe": 440, "KOKO": 1500, "606 Jazz Club": 180, "606 Club": 180,
        "World Heart Beat": 120, "Toulouse Lautrec": 150,
        "East Side Jazz Club": 120, "Bull's Head Barnes": 150,
        "Ladbroke Hall": 220, "Vortex Jazz Club": 90,
        "PizzaExpress Jazz Club": 120, "Jazz Café POSK": 100,
        "Café OTO": 80,
    }
    INTL = ["grammy", "mercury prize", "international", "new york",
            "paris", "worldwide", "european tour"]

    score = 0
    ep = g.get("editors_pick")
    if ep is True or ep == "TRUE": score += 20
    if g.get("special_occasion"):  score += 8
    stage = g.get("stage") or ""
    if g.get("venue_name") in PREMIUM_VENUES and stage not in SUB_ROOMS:
        score += 6
    tier = g.get("venue_tier", "1")
    if tier == "2": score -= 2
    if tier == "3": score -= 5

    try:
        p = float((g.get("price_from") or "").replace("£", "").replace(",", ""))
        if p >= 30:   score += 6
        elif p >= 20: score += 4
        elif p >= 12: score += 2
        elif p >= 8:  score += 1
    except (ValueError, TypeError):
        pass

    if g.get("format_tags") == "Concert Hall": score += 3

    text = ((g.get("description") or "") + " " + (g.get("artist_name") or "")).lower()
    if any(s in text for s in INTL): score += 5

    if g.get("venue_name") == "Ronnie Scott's" and stage == "Main Stage": score += 4
    if g.get("venue_name") == "Vortex Jazz Club": score += 2

    if stage not in SUB_ROOMS:
        cap = VENUE_CAPACITY.get(g.get("venue_name") or "", 0)
        if cap >= 500:   score += 3
        elif cap >= 200: score += 2
        elif cap >= 100: score += 1

    return score


def format_date_heading(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%A %-d %B")
    except ValueError:
        return date_str


def is_today(date_str: str) -> bool:
    return date_str == date.today().isoformat()


def is_tomorrow(date_str: str) -> bool:
    from datetime import timedelta
    return date_str == (date.today() + timedelta(days=1)).isoformat()


def render_gig_card(g: dict) -> str:
    is_pick = g.get("editors_pick") is True or g.get("editors_pick") == "TRUE"
    tags = []
    if g.get("special_occasion"):
        tags.append(f'<span class="tag tag-special">{esc(g["special_occasion"])}</span>')
    if g.get("genre_tier1"):
        tags.append(f'<span class="tag">{esc(g["genre_tier1"])}</span>')
    if g.get("band_format"):
        tags.append(f'<span class="tag tag-format">{esc(g["band_format"])}</span>')
    if g.get("format_tags"):
        tags.append(f'<span class="tag">{esc(g["format_tags"])}</span>')
    price_lower = (g.get("price_from") or "").lower()
    if price_lower == "free":
        tags.append('<span class="tag tag-free">Free</span>')

    price_str = g.get("price_full_text") or g.get("price_from") or ""
    time_str  = g.get("start_time") or ""
    desc      = g.get("description") or ""
    stage     = f' · {esc(g["stage"])}' if g.get("stage") else ""
    hood      = f' · <span>{esc(g["neighbourhood"])}</span>' if g.get("neighbourhood") else ""

    ticket_btn = (
        f'<a href="{esc(g["ticket_url"])}" target="_blank" rel="noopener" '
        f'class="gig-ticket-link">Book →</a>'
        if g.get("ticket_url") else ""
    )

    pick_class = "editors-pick" if is_pick else ""

    return f"""    <div class="gig-card {pick_class}" data-gig-id="{esc(g.get('gig_id',''))}">
      <div class="gig-main">
        <div class="gig-artist">{esc(g["artist_name"])}</div>
        <div class="gig-venue">
          <span class="gig-venue-name">{esc(g["venue_name"])}</span>{stage}{hood}
        </div>
        {f'<div class="gig-description">{esc(desc)}</div>' if desc else ''}
        <div class="gig-tags">{''.join(tags)}</div>
      </div>
      <div class="gig-aside">
        {f'<div class="gig-time">{esc(time_str)}</div>' if time_str else ''}
        {f'<div class="gig-price">{esc(price_str)}</div>' if price_str else ''}
        {ticket_btn}
      </div>
    </div>"""


def render_listings(gigs: list) -> str:
    # Group by date
    grouped: dict[str, list] = {}
    for g in gigs:
        grouped.setdefault(g["date"], []).append(g)

    parts = []
    for date_str in sorted(grouped.keys()):
        day_gigs = sorted(grouped[date_str], key=gig_score, reverse=True)
        heading = format_date_heading(date_str)
        meta = ""
        if is_today(date_str):   meta = '<div class="date-group-meta">Tonight</div>'
        elif is_tomorrow(date_str): meta = '<div class="date-group-meta">Tomorrow</div>'

        cards = "\n".join(render_gig_card(g) for g in day_gigs)
        parts.append(f"""            <div class="date-group">
              <div class="date-group-header">
                <div class="date-group-day">{heading}</div>
                {meta}
              </div>
              {cards}
            </div>""")

    today = date.today().isoformat()
    count = len(gigs)
    return f'<!-- PRERENDERED:{today} -->\n' + "\n".join(parts)


def prerender_gigs_html():
    gigs = load_gigs()
    gigs_sorted = sorted(gigs, key=lambda g: (g["date"], -gig_score(g)))
    listings_html = render_listings(gigs_sorted)

    with open(ROOT / "gigs.html") as f:
        html = f.read()

    # Replace content inside <div class="listings" id="listings">...</div>
    new_html = re.sub(
        r'(<div class="listings" id="listings">).*?(</div>\s*\n\s*</div>\s*\n\s*</main>)',
        lambda m: m.group(1) + "\n" + listings_html + "\n            " + m.group(2),
        html,
        flags=re.DOTALL,
    )

    if new_html == html:
        print("  WARNING: listings replacement pattern not matched")
        return False

    with open(ROOT / "gigs.html", "w") as f:
        f.write(new_html)

    today = date.today().isoformat()
    print(f"  gigs.html pre-rendered: {len(gigs)} gigs ({today})")
    return True


if __name__ == "__main__":
    prerender_gigs_html()
