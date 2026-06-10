"""
prerender.py — Static HTML pre-renderer for The London Jazz List
Generates gig cards as real HTML inside gigs.html so Google
can index all artist names, venues and dates on first crawl.

Run nightly after run_all.py (wired into nightly.yml).
"""

import json, html, re
from datetime import date, datetime
from pathlib import Path
from itertools import groupby

TODAY     = date.today().isoformat()
ROOT      = Path(__file__).parent
DATA_FILE = ROOT / "data" / "gigs.json"
GIGS_HTML = ROOT / "gigs.html"

VENUE_ADDRESSES = {
    "Vortex Jazz Club":    {"streetAddress": "11 Gillett Square",    "addressLocality": "Dalston",          "postalCode": "N16 8AZ"},
    "Ronnie Scott's":     {"streetAddress": "47 Frith Street",      "addressLocality": "Soho",             "postalCode": "W1D 4HT"},
    "606 Jazz Club":       {"streetAddress": "90 Lots Road",         "addressLocality": "Chelsea",          "postalCode": "SW10 0QD"},
    "606 Club":            {"streetAddress": "90 Lots Road",         "addressLocality": "Chelsea",          "postalCode": "SW10 0QD"},
    "Cadogan Hall":        {"streetAddress": "5 Sloane Terrace",     "addressLocality": "Chelsea",          "postalCode": "SW1X 9DQ"},
    "Wigmore Hall":        {"streetAddress": "36 Wigmore Street",    "addressLocality": "Marylebone",       "postalCode": "W1U 2BP"},
    "Royal Albert Hall":   {"streetAddress": "Kensington Gore",      "addressLocality": "South Kensington", "postalCode": "SW7 2AP"},
    "Royal Festival Hall": {"streetAddress": "Belvedere Road",       "addressLocality": "South Bank",       "postalCode": "SE1 8XX"},
    "King's Place":       {"streetAddress": "90 York Way",          "addressLocality": "King's Cross",    "postalCode": "N1 9AG"},
    "Union Chapel":        {"streetAddress": "19b Compton Terrace",  "addressLocality": "Islington",        "postalCode": "N1 2UN"},
    "World Heart Beat":    {"streetAddress": "3 Ponton Road",        "addressLocality": "Nine Elms",        "postalCode": "SW11 7BD"},
    "Ladbroke Hall":       {"streetAddress": "Ladbroke Road",        "addressLocality": "Notting Hill",     "postalCode": "W11 3NW"},
    "East Side Jazz Club": {"streetAddress": "2 Station Road",       "addressLocality": "Leytonstone",      "postalCode": "E11 1QW"},
    "Lauderdale House":    {"streetAddress": "Highgate Hill",        "addressLocality": "Highgate",         "postalCode": "N6 5HG"},
    "Barbican":            {"streetAddress": "Silk Street",          "addressLocality": "Barbican",         "postalCode": "EC2Y 8DS"},
    "Barbican Centre":     {"streetAddress": "Silk Street",          "addressLocality": "Barbican",         "postalCode": "EC2Y 8DS"},
    "EartH Theatre":       {"streetAddress": "11 Stoke Newington Rd","addressLocality": "Hackney",          "postalCode": "N16 8BH"},
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def to_iso_time(t):
    if not t: return ""
    m = re.match(r"(\d{1,2})[.:]?(\d{2})\s*(am|pm)?", str(t), re.I)
    if not m:
        m2 = re.match(r"(\d{1,2})\s*(am|pm)", str(t), re.I)
        if m2:
            h, sfx = int(m2.group(1)), m2.group(2).lower()
            if sfx == "pm" and h != 12: h += 12
            if sfx == "am" and h == 12: h = 0
            return f"T{h:02d}:00:00"
        return ""
    h, mn = int(m.group(1)), m.group(2)
    sfx = (m.group(3) or "").lower()
    if sfx == "pm" and h != 12: h += 12
    if sfx == "am" and h == 12: h = 0
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
            "name": g.get("venue_name", "") + (f" \u2014 {stage}" if stage else ""),
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
            "@type": "Offer", "price": price, "priceCurrency": "GBP",
            "availability": "https://schema.org/InStock",
            "url": g.get("ticket_url", "") or "https://londonjazzlist.co.uk/gigs.html"
        }
    return json.dumps(schema)


def fmt_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%A %-d %B")
    except:
        return d


def render_card(g):
    is_pick = g.get("editors_pick") is True or g.get("editors_pick") == "TRUE"
    tags = []
    if g.get("special_occasion"): tags.append(f'<span class="tag tag-special">{esc(g["special_occasion"])}</span>')
    if g.get("genre_tier1"):      tags.append(f'<span class="tag">{esc(g["genre_tier1"])}</span>')
    if g.get("band_format"):      tags.append(f'<span class="tag tag-format">{esc(g["band_format"])}</span>')
    if g.get("format_tags"):      tags.append(f'<span class="tag">{esc(g["format_tags"])}</span>')
    price = g.get("price_from", "") or ""
    if price.lower() == "free":   tags.append('<span class="tag tag-free">Free</span>')
    stage  = f' &middot; {esc(g["stage"])}' if g.get("stage") else ""
    hood   = f' &middot; <span>{esc(g["neighbourhood"])}</span>' if g.get("neighbourhood") else ""
    desc   = f'<div class="gig-description">{esc(g["description"])}</div>' if g.get("description") else ""
    time_  = f'<div class="gig-time">{esc(g["start_time"])}</div>' if g.get("start_time") else ""
    price_ = f'<div class="gig-price">{esc(price)}</div>' if price and price.lower() != "free" else ""
    btn    = (f'<a href="{esc(g["ticket_url"])}" target="_blank" rel="noopener" class="gig-ticket-link">Book &rarr;</a>'
              if g.get("ticket_url") else "")
    sch    = make_schema(g)
    pick_class = "editors-pick" if is_pick else ""
    return (
        f'    <script type="application/ld+json">{sch}</script>\n'
        f'    <div class="gig-card {pick_class}">\n'
        f'      <div class="gig-main">\n'
        f'        <div class="gig-artist">{esc(g["artist_name"])}</div>\n'
        f'        <div class="gig-venue"><span class="gig-venue-name">{esc(g["venue_name"])}</span>{stage}{hood}</div>\n'
        f'        {desc}\n'
        f'        <div class="gig-tags">{"".join(tags)}</div>\n'
        f'      </div>\n'
        f'      <div class="gig-aside">{time_}{price_}{btn}</div>\n'
        f'    </div>'
    )


def prerender():
    with open(DATA_FILE) as f:
        all_gigs = json.load(f)

    gigs = [
        g for g in all_gigs
        if g.get("date", "") >= TODAY
        and not g.get("hidden")
        and (g.get("price_from", "") or "").lower() != "free"
    ]
    gigs.sort(key=lambda g: (g.get("date", ""), not (g.get("editors_pick") is True)))

    groups = []
    for d, day_gigs in groupby(gigs, key=lambda g: g["date"]):
        dl = list(day_gigs)
        meta = '<div class="date-group-meta">Tonight</div>' if d == TODAY else ""
        cards = "\n".join(render_card(g) for g in dl)
        groups.append(
            f'            <div class="date-group">\n'
            f'              <div class="date-group-header">\n'
            f'                <div class="date-group-day">{fmt_date(d)}</div>\n'
            f'                {meta}\n'
            f'              </div>\n'
            f'{cards}\n'
            f'            </div>'
        )

    static_listings = "\n".join(groups)
    count = len(gigs)

    with open(GIGS_HTML) as f:
        page = f.read()

    # Update result count
    page = re.sub(
        r'<div class="result-count" id="result-count">[^<]*</div>',
        f'<div class="result-count" id="result-count">{count} gigs</div>',
        page
    )

    # Replace listings div using depth-counting (avoids regex backslash issues)
    MARKER = '<div class="listings" id="listings">' 
    start_idx = page.find(MARKER)
    if start_idx < 0:
        print("ERROR: listings div not found in gigs.html")
        return

    pos = start_idx + len(MARKER)
    depth = 1
    end_idx = pos
    while pos < len(page) and depth > 0:
        if page[pos:pos+4] == "<div":
            depth += 1
        elif page[pos:pos+6] == "</div>":
            depth -= 1
            if depth == 0:
                end_idx = pos + 6
                break
        pos += 1

    new_block = (
        f'{MARKER}\n'
        f'<!-- PRERENDERED:{TODAY} -->\n'
        f'{static_listings}\n'
        f'      </div>'
    )
    page = page[:start_idx] + new_block + page[end_idx:]

    with open(GIGS_HTML, "w") as f:
        f.write(page)

    print(f"prerender.py: {count} gig cards pre-rendered ({TODAY})")


if __name__ == "__main__":
    prerender()
