"""
scraper_musicglue.py — MusicGlue venues
Karamel: scrapes the dedicated jazz category page across all pages.
Jazz events are presented as "KAIYO presents", "Women in Jazz Media" etc.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import fetch, gig, load, save, merge_gigs, clean_date, is_future

KARAMEL_JAZZ_URL = "https://www.musicglue.com/karamel/whats-on-at-karamel/categories/jazz"

# These are the jazz promoters/curators at Karamel
JAZZ_PRESENTERS = [
    "kaiyo", "women in jazz media", "collage presents jazz",
    "jazz stories", "efg london jazz", "belonging: a collective",
]

# Non-jazz events to skip even if they appear on the jazz page
SKIP_TITLES = [
    "singing mamas", "bolly dance", "vegan sunday roast",
    "sacred frequencies", "wellness", "circle creatives",
    "closed for a private", "private event",
    "belonging: a collective experience",  # art/community not jazz
]


def _is_jazz_event(title: str) -> bool:
    """Return True if the event title indicates a jazz event."""
    t = title.lower()
    # Skip non-jazz
    if any(s in t for s in SKIP_TITLES):
        return False
    # Keep if jazz presenter
    if any(p in t for p in JAZZ_PRESENTERS):
        return True
    # Keep if explicit jazz keywords
    if any(k in t for k in ["jazz", "improvisation", "bebop", "swing",
                              "saxophone", "quartet", "quintet", "trio"]):
        return True
    return False


def scrape_karamel() -> list:
    print("  Scraping Karamel (jazz page)...")
    results = []
    
    # Scrape all pages
    for page_num in range(1, 6):  # up to 5 pages
        if page_num == 1:
            url = KARAMEL_JAZZ_URL
        else:
            url = f"{KARAMEL_JAZZ_URL}/page/{page_num}"
        
        soup = fetch(url)
        if not soup:
            break
        
        # Check if page has events
        text = soup.get_text(separator="\n", strip=True)
        if "no events" in text.lower() or len(text) < 500:
            break
        
        # Each event has: date, time, title, price, tickets link
        # MusicGlue structure: event titles are in links with /events/ in href
        event_links = soup.select("a[href*='/karamel/events/']")
        seen = set()
        
        for link in event_links:
            href = link.get("href", "")
            if not href or href in seen:
                continue
            # Skip basket/nav links
            if "basket" in href or "whats-on" in href:
                continue
            seen.add(href)
            
            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            
            # Clean "Collage presents: " prefix to get the actual artist/event name
            clean_title = re.sub(r'^Collage (?:presents:|Community presents:|x .+? presents:)\s*', 
                                  '', title, flags=re.IGNORECASE).strip()
            
            if not _is_jazz_event(clean_title) and not _is_jazz_event(title):
                continue
            
            # Get surrounding context for date/price
            parent = link.parent
            while parent and parent.name not in ("div", "li", "article", "tr", "body"):
                parent = parent.parent
            context = parent.get_text(separator=" ", strip=True) if parent else ""
            
            # Date — MusicGlue format: "Wed, Jun 10, 2026"
            date_m = re.search(
                r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+"
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
                r"(\d{1,2}),?\s+(\d{4})",
                context, re.IGNORECASE
            )
            if not date_m:
                continue
            
            date_str = clean_date(
                f"{date_m.group(3)} {date_m.group(2)} {date_m.group(4)}"
            )
            if not is_future(date_str):
                continue
            
            # Time
            time_m = re.search(r"(\d{1,2}:\d{2})\s*(PM|AM)?", context, re.IGNORECASE)
            start_time = time_m.group(0) if time_m else ""
            
            # Price
            price_m = re.search(r"£(\d+)", context)
            price = f"£{price_m.group(1)}" if price_m else ""
            if "free entry" in context.lower() or "free taster" in context.lower():
                price = "Free"
            
            full_url = href if href.startswith("http") else f"https://www.musicglue.com{href}"
            
            results.append(gig(
                artist_name=clean_title,
                venue_name="Karamel",
                date=date_str,
                start_time=start_time,
                price_from=price,
                ticket_url=full_url,
                source_url=KARAMEL_JAZZ_URL,
                zone="North",
                neighbourhood="Wood Green",
                format_tags="Jazz Club",
                genre_tier1="Contemporary Jazz",
                venue_tier="3",
            ))
        
        # Check if there's a next page
        next_link = soup.find("a", string=re.compile(r"Next", re.IGNORECASE))
        if not next_link:
            break
    
    # Deduplicate by gig_id
    seen_ids = set()
    unique = []
    for r in results:
        if r["gig_id"] not in seen_ids:
            unique.append(r)
            seen_ids.add(r["gig_id"])
    
    print(f"    Karamel: {len(unique)} jazz gigs")
    return unique


def scrape() -> list:
    print("Scraping MusicGlue venues...")
    results = scrape_karamel()
    
    # Add Bull's Head Barnes (also on MusicGlue)
    results.extend(scrape_bulls_head())
    
    print(f"  Total MusicGlue: {len(results)} gigs")
    return results


def scrape_bulls_head() -> list:
    """Bull's Head Barnes — dedicated jazz venue on MusicGlue."""
    print("  Scraping Bull's Head Barnes...")
    url = "https://tickets.thebullsheadbarnes.com/live-music"
    soup = fetch(url)
    if not soup:
        return []
    
    results = []
    event_links = soup.select("a[href*='/events/']")
    seen = set()
    
    for link in event_links:
        href = link.get("href", "")
        if not href or href in seen:
            continue
        seen.add(href)
        
        title = link.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        # Skip nav
        if any(s in title.lower() for s in ["live music", "tickets", "about", "contact"]):
            continue
        
        parent = link.parent
        while parent and parent.name not in ("div", "li", "article", "tr", "body"):
            parent = parent.parent
        context = parent.get_text(separator=" ", strip=True) if parent else ""
        
        date_m = re.search(
            r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
            r"(\d{1,2}),?\s+(\d{4})",
            context, re.IGNORECASE
        )
        if not date_m:
            continue
        
        date_str = clean_date(f"{date_m.group(3)} {date_m.group(2)} {date_m.group(4)}")
        if not is_future(date_str):
            continue
        
        time_m  = re.search(r"(\d{1,2}:\d{2})\s*(PM|AM)?", context, re.IGNORECASE)
        price_m = re.search(r"£(\d+)", context)
        full_url = href if href.startswith("http") else f"https://tickets.thebullsheadbarnes.com{href}"
        
        results.append(gig(
            artist_name=title,
            venue_name="Bull's Head Barnes",
            date=date_str,
            start_time=time_m.group(0) if time_m else "",
            price_from=f"£{price_m.group(1)}" if price_m else "",
            ticket_url=full_url,
            source_url=url,
            zone="West / South West",
            neighbourhood="Barnes",
            format_tags="Jazz Club",
            genre_tier1="Mainstream / Swing",
            venue_tier="1",
        ))
    
    # Deduplicate
    seen_ids = set()
    unique = []
    for r in results:
        if r["gig_id"] not in seen_ids:
            unique.append(r)
            seen_ids.add(r["gig_id"])
    
    print(f"    Bull's Head: {len(unique)} gigs")
    return unique


def run():
    new_gigs = scrape()
    if not new_gigs:
        print("  No gigs found")
        return
    existing = load("gigs")
    merged, added = merge_gigs(existing, new_gigs)
    save("gigs", merged)
    print(f"  Added {added} new MusicGlue gigs")


if __name__ == "__main__":
    run()
