"""
prerender.py — Static HTML pre-renderer for The London Jazz List
Generates gig cards as real HTML inside gigs.html so Google
can index all artist names, venues and dates on first crawl
without executing JavaScript.

Run as part of the nightly workflow AFTER run_all.py:
    python prerender.py

Reads:  data/gigs.json
Writes: gigs.html  (replaces the <div id="listings"> content with static cards)

The page still loads data.js and utils.js for interactive filtering —
the static cards are hidden by CSS once JS runs, replaced by the JS-rendered
versions. This gives Google the content while users still get the live UI.
"""

import json, html, re, os
from datetime import date, datetime
from pathlib import Path

TODAY      = date.today().isoformat()
ROOT       = Path(__file__).parent
DATA_FILE  = ROOT / "data" / "gigs.json"
GIGS_HTML  = ROOT / "gigs.html"

# Venue addresses for schema
VENUE_ADDRESSES = {
    "Vortex Jazz Club":       {"streetAddress": "11 Gillett Square",    "addressLocality": "Dalston",       "postalCode": "N16 8AZ"},
    "Ronnie Scott's":         {"streetAddress": "47 Frith Street",      "addressLocality": "Soho",          "postalCode": "W1D 4HT"},
    "606 Jazz Club":          {"streetAddress": "90 Lots Road",         "addressLocality": "Chelsea",       "postalCode": "SW10 0QD"},
    "606 Club":               {"streetAddress": "90 Lots Road",         "addressLocality": "Chelsea",       "postalCode": "SW10 0QD"},
    "Barbican":               {"streetAddress": "Silk Street",          "addressLocality": "Barbican",      "postalCode": "EC2Y 8DS"},
    "Barbican Centre":        {"streetAddress": "Silk Street",          "addressLocality": "Barbican",      "postalCode": "EC2Y 8DS"},
    "Cadogan Hall":           {"streetAddress": "5 Sloane Terrace",     "addressLocality": "Chelsea",       "postalCode": "SW1X 9DQ"},
    "Royal Albert Hall":      {"streetAddress": "Kensington Gore",      "addressLocality": "South Kensington","postalCode": "SW7 2AP"},
    "Wigmore Hall":           {"streetAddress": "36 Wigmore Street",    "addressLocality": "Marylebone",    "postalCode": "W1U 2BP"},
    "King's Place":           {"streetAddress": "90 York Way",          "addressLocality": "King's Cross",  "postalCode": "N1 9AG"},
    "Royal Festival Hall":    {"streetAddress": "Belvedere Road",       "addressLocality": "South Bank",    "postalCode": "SE1 8XX"},
    "Queen Elizabeth Hall":   {"streetAddress": "Belvedere Road",       "addressLocality": "South Bank",    "postalCode": "SE1 8XX"},
    "Lauderdale House":       {"streetAddress": "Highgate Hill",        "addressLocality": "Highgate",      "postalCode": "N6 5HG"},
    "Union Chapel":           {"streetAddress": "19b Compton Terrace",  "addressLocality": "Islington",     "postalCode": "N1 2UN"},
    "EartH Theatre":          {"streetAddress": "11 Stoke Newington Rd","addressLocality": "Hackney",       "postalCode": "N16 8BH"},
    "World Heart Beat":       {"streetAddress": "3 Ponton Road",        "addressLocality": "Nine Elms",     "postalCode": "SW11 7BD"},
    "Ladbroke Hall":          {"streetAddress": "Ladbroke Road",        "addressLocality": "Notting Hill",  "postalCode": "W11 3NW"},
    "East Side Jazz Club":    {"streetAddress": "2 Station Road",       "addressLocality": "Leytonstone",   "postalCode": "E11 1QW"},
}

def esc(s):
    return html.escape(str(s or ""), quote=True)

def to_iso_time(t):
    if not t:
        return ""
    m = re.match(r"(\d{1,2})[.:](\d{2})\s*(am|pm)?", str(t), re.I)
    if not m:
        m2 = re.match(r"(\d{1,2})\s*(am|pm)", str(t), re.I)
        if m2:
            h, suffix = int(m2.group(1)), m2.group(2).lower()
            if suffix == "pm" and h != 12: h += 12
            if suffix == "am" and h == 12: h = 0
            return f"T{h:02d}:00:00"
        return ""
    h, mn = int(m.group(1)), m.group(2)
    suffix = (m.group(3) or "").lower()
    if suffix == "pm" and h != 12: h += 12
    if suffix == "am" and h == 12: h = 0
    return f"T{h:02d}:{mn}:00"

def make_schema(g):
    addr = VENUE_ADDRESSES.get(g.get("venue_name", ""), {})
    stage = g.get("stage", "") or ""
    schema = {
        "@context": "https://schema.org",
        "@type": "MusicEvent",
        "name": g.get("artist_name", ""),
        "startDate": g.get("date", "") + to_iso_time(g.get("start_time")),
        "location": {
            "@type": "MusicVenue",
            "name": g.get("venue_name", "") + (f" — {stage}" if stage else ""),
            "address": {
                "@type": "PostalAddress",
                "streetAddress": addr.get("streetAddress", ""),
                "addressLocality": addr.get("addressLocality", g.get("neighbourhood", "London")),
                "postalCode": addr.get("postalCode", ""),
                "addressCountry": "GB"
            }
        },
        "description": g.get("description", ""),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "performer": {"@type": "MusicGroup", "name": g.get("artist_name", "")},
        "organizer": {"@type": "Organization", "name": g.get("venue_name", "")},
        "url": g.get("ticket_url", "") or "https://londonjazzlist.co.uk/gigs.html",
    }
    price = re.sub(r"[^0-9.]", "", g.get("price_from", "") or "")
    if price:
        schema["offers"] = {
            "@type": "Offer",
            "price": price,
            "priceCurrency": "GBP",
            "availability": "https://schema.org/InStock",
            "url": g.get("ticket_url", "") or "https://londonjazzlist.co.uk/gigs.html"
        }
    return json.dumps(schema)

def format_date_heading(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%A %-d %B")
    except:
        return date_str

def render_gig_card(g):
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
    price = g.get("price_from", "") or ""
    if price.lower() == "free":
        tags.append('<span class="tag tag-free">Free</span>')

    stage = f' · {esc(g["stage"])}' if g.get("stage") else ""
    neighbourhood = f' · <span>{esc(g["neighbourhood"])}</span>' if g.get("neighbourhood") else ""
    desc = f'<div class="gig-description">{esc(g["description"])}</div>' if g.get("description") else ""
    time_str = f'<div class="gig-time">{esc(g["start_time"])}</div>' if g.get("start_time") else ""
    price_str = f'<div class="gig-price">{esc(price)}</div>' if price and price.lower() != "free" else ""
    ticket_btn = (f'<a href="{esc(g["ticket_url"])}" target="_blank" rel="noopener" '
                  f'class="gig-ticket-link">Book →</a>') if g.get("ticket_url") else ""
    schema = make_schema(g)

    return f"""    <script type="application/ld+json">{schema}</script>
    <div class="gig-card {'editors-pick' if is_pick else ''}">
      <div class="gig-main">
        <div class="gig-artist">{esc(g["artist_name"])}</div>
        <div class="gig-venue">
          <span class="gig-venue-name">{esc(g["venue_name"])}</span>{stage}{neighbourhood}
        </div>
        {desc}
        <div class="gig-tags">{''.join(tags)}</div>
      </div>
      <div class="gig-aside">
        {time_str}
        {price_str}
        {ticket_btn}
      </div>
    </div>"""

def prerender():
    with open(DATA_FILE) as f:
        all_gigs = json.load(f)

    # Filter: future, not hidden, not free (free belongs on /free.html)
    gigs = [
        g for g in all_gigs
        if g.get("date", "") >= TODAY
        and not g.get("hidden")
        and (g.get("price_from") or "").lower() != "free"
    ]

    # Sort by date, editors_pick within day (mirrors JS sortGigsWithinDay)
    gigs.sort(key=lambda g: (g.get("date", ""), not (g.get("editors_pick") is True)))

    # Group by date
    from itertools import groupby
    cards_html = []
    for date_str, day_gigs in groupby(gigs, key=lambda g: g["date"]):
        day_list = list(day_gigs)
        heading = format_date_heading(date_str)
        is_today = date_str == TODAY
        meta = '<div class="date-group-meta">Tonight</div>' if is_today else ""
        cards_html.append(f"""            <div class="date-group">
              <div class="date-group-header">
                <div class="date-group-day">{heading}</div>
                {meta}
              </div>
              {''.join(render_gig_card(g) for g in day_list)}
            </div>""")

    static_listings = "\n".join(cards_html)
    count = len(gigs)

    # Read current gigs.html
    with open(GIGS_HTML) as f:
        page = f.read()

    # Replace result-count
    page = re.sub(
        r'<div class="result-count" id="result-count">[^<]*</div>',
        f'<div class="result-count" id="result-count">{count} gigs</div>',
        page
    )

    # Replace listings content — preserve the div itself, replace inner content
    # Inject a noscript-friendly static version + marker for JS to replace
    static_block = f"""<div class="listings" id="listings">
<!-- PRERENDERED:{TODAY} — JS will replace this with filtered/live version -->
{static_listings}
      </div>"""

    page = re.sub(
        r'<div class="listings" id="listings">.*?</div>\s*(?=\s*</div>\s*</main>)',
        static_block + "\n      ",
        page,
        flags=re.DOTALL
    )

    with open(GIGS_HTML, "w") as f:
        f.write(page)

    print(f"prerender.py: {count} gigs pre-rendered into gigs.html ({TODAY})")

if __name__ == "__main__":
    prerender()
