/**
 * data.js — fetches JSON data files
 * Files are served locally from /data/ folder (copied from scrapers by GitHub Actions)
 */

const BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? '/data'
  : '/data';  // Same path — Netlify serves from repo root

const URLS = {
  gigs:         `${BASE}/gigs.json`,
  jam_sessions: `${BASE}/jam_sessions.json`,
  brunches:     `${BASE}/brunches.json`,
  free_entry:   `${BASE}/free_entry.json`,
  festivals:    `${BASE}/festivals.json`,
  dining:       `${BASE}/dining.json`,
};

const _cache = {};

async function fetchData(category) {
  if (_cache[category]) return _cache[category];
  try {
    const res = await fetch(URLS[category]);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _cache[category] = data;
    return data;
  } catch (e) {
    console.error(`Failed to fetch ${category}:`, e);
    return [];
  }
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long'
  });
}

function formatDateShort(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short'
  });
}

function isToday(dateStr) {
  return dateStr === today();
}

function isTomorrow(dateStr) {
  const t = new Date();
  t.setDate(t.getDate() + 1);
  return dateStr === t.toISOString().slice(0, 10);
}

function isThisWeek(dateStr) {
  const t = new Date();
  const end = new Date();
  end.setDate(t.getDate() + 7);
  const d = new Date(dateStr + 'T12:00:00');
  return d >= t && d <= end;
}

function groupByDate(gigs) {
  const groups = {};
  for (const g of gigs) {
    if (!groups[g.date]) groups[g.date] = [];
    groups[g.date].push(g);
  }
  return groups;
}

function uniqueValues(arr, field) {
  const vals = arr
    .map(x => x[field])
    .filter(Boolean)
    .flatMap(v => v.includes(',') ? v.split(',').map(s => s.trim()) : [v]);
  return [...new Set(vals)].sort();
}


// ── Gig ranking ───────────────────────────────────────────────
// Scores each gig so better gigs appear first within each day.

const PREMIUM_VENUES = new Set([
  "Barbican Centre", "Cadogan Hall", "Royal Albert Hall",
  "Royal Festival Hall", "Wigmore Hall", "Union Chapel",
  "EartH Theatre", "Ronnie Scott's", "Pizza Express Jazz Club",
]);

const INTERNATIONAL_SIGNALS = [
  " us ", "u.s.", "american", "new york", "nyc", "european tour",
  "international", "grammy", "first uk", "rare uk", "uk debut",
  "world tour", "mercury prize",
];

function gigScore(g) {
  let score = 0;

  // Editor's pick — highest priority
  if (g.editors_pick === true || g.editors_pick === "TRUE") score += 20;

  // Special occasion
  if (g.special_occasion) score += 8;

  // Venue tier
  if (g.venue_tier === "2" || PREMIUM_VENUES.has(g.venue_name)) score += 6;

  // Price signals (higher price = more significant artist)
  const price = parseFloat((g.price_from || "").replace(/[^0-9.]/g, ""));
  if (!isNaN(price)) {
    if (price >= 30) score += 6;
    else if (price >= 20) score += 4;
    else if (price >= 12) score += 2;
    else if (price >= 8)  score += 1;
  }

  // Format
  if (g.format_tags === "Concert Hall") score += 3;

  // International signals in description or artist name
  const text = ((g.description || "") + " " + (g.artist_name || "")).toLowerCase();
  if (INTERNATIONAL_SIGNALS.some(s => text.includes(s))) score += 5;

  // Two shows in a day already flagged via editors_pick, but also detect here
  // (handled server-side now via auto picks)

  // Ronnie's main stage vs late show
  if (g.venue_name === "Ronnie's Scott's" && g.stage === "Main Stage") score += 4;
  if (g.venue_name === "Ronnie Scott's" && g.stage === "Main Stage") score += 4;

  // Vortex premium: two shows detected server-side via editors_pick
  // But also boost Vortex generally over pub gigs
  if (g.venue_name === "Vortex Jazz Club") score += 2;

  return score;
}

function sortGigsWithinDay(gigs) {
  return [...gigs].sort((a, b) => {
    const scoreDiff = gigScore(b) - gigScore(a);
    if (scoreDiff !== 0) return scoreDiff;
    // Tiebreak: earlier start time first
    return (a.start_time || "").localeCompare(b.start_time || "");
  });
}
