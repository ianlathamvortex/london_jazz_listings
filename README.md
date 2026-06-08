# London Jazz Scrapers

Automated scrapers for [London Jazz Listings] — a comprehensive guide to jazz gigs, jam sessions, brunches and free entry events in London.

## Structure

```
├── scrapers/
│   ├── utils.py                  Shared helpers (fetch, dedupe, data model)
│   ├── scraper_ronnies.py        Ronnie Scott's
│   ├── scraper_606.py            606 Club
│   ├── scraper_vortex.py         Vortex Jazz Club
│   ├── scraper_pizzaexpress.py   PizzaExpress Jazz Club + Pheasantry
│   ├── scraper_musicglue.py      MusicGlue venues (Karamel etc)
│   ├── scraper_serious.py        Serious Promotions (Barbican, Cadogan, RAH etc)
│   ├── scraper_venues.py         Smaller venues (East Side, Green Note, OTO etc)
│   └── scraper_ukjazznews.py     UK Jazz News weekly newsletter parser
├── enricher/
│   └── enricher.py               Claude API description generator
├── data/
│   ├── gigs.json                 All scraped gigs
│   ├── jam_sessions.json         Weekly jam sessions (curated)
│   ├── brunches.json             Jazz brunches (curated)
│   ├── free_entry.json           Free entry events
│   └── festivals.json            Festivals
├── .github/workflows/
│   └── nightly.yml               GitHub Actions schedule (midnight nightly)
├── run_all.py                    Master runner
└── requirements.txt
```

## Setup

### GitHub Secrets required
| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key for description generation |

### Run locally
```bash
pip install -r requirements.txt
python run_all.py
```

### Manual trigger
Go to **Actions** tab → **Nightly Jazz Scraper** → **Run workflow**

## Data format

Each gig in `data/gigs.json` has:
```json
{
  "gig_id": "billy-cobham-ronnie-scotts-2026-06-08",
  "date": "2026-06-08",
  "start_time": "20:00",
  "artist_name": "Billy Cobham with the Guy Barker Big Band",
  "venue_name": "Ronnie Scott's",
  "venue_tier": "1",
  "zone": "Central",
  "neighbourhood": "Soho",
  "ticket_url": "https://www.ronniescotts.co.uk/...",
  "price_from": "£35",
  "genre_tier1": "Big Band",
  "format_tags": "Jazz Club",
  "description": "...",
  "editors_pick": false,
  "special_occasion": ""
}
```

## Adding a new venue

1. Add a new entry to `VENUES` dict in `scraper_venues.py`
2. Or create a dedicated scraper file if the venue needs custom parsing
3. Add the scraper to the `SCRAPERS` list in `run_all.py`
4. Test locally: `python scrapers/scraper_yourfile.py`

## Notes

- Scrapers are resilient — if a site changes structure they log a warning and continue
- Deduplication is by `gig_id` (artist + venue + date slug)
- `editors_pick`, `editors_note` and `star_rating` fields are never overwritten by scrapers
- Description enrichment is skipped if `ANTHROPIC_API_KEY` is not set
