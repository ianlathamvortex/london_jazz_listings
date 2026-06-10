/**
 * data.js — fetches JSON data files
 * Files are at the repo root, served by Netlify from /
 */

const URLS = {
  gigs:         '/gigs.json',
  jam_sessions: '/jam_sessions.json',
  brunches:     '/brunches.json',
  free_entry:   '/free_entry.json',
  festivals:    '/festivals.json',
  dining:       '/dining.json',
};

const _cache = {};

async function fetchData(category) {
  if (_cache[category]) return _cache[category];
  try {
    const res = await fetch(URLS[category]);
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${URLS[category]}`);
    const data = await res.json();
    _cache[category] = data;
    return data;
  } catch (e) {
    console.error(`Failed to fetch ${category}:`, e);
    return [];
  }
}

// ── Date helpers ──────────────────────────────────────────────

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

const PREMIUM_VENUES = new Set([
  "Barbican Centre", "Cadogan Hall", "Royal Albert Hall",
  "Royal Festival Hall", "Wigmore Hall", "Union Chapel",
  "EartH Theatre", "Ronnie Scott's",
]);

const INTERNATIONAL_SIGNALS = [
  " us ", "u.s.", "american", "new york", "nyc", "european tour",
  "international", "grammy", "first uk", "rare uk", "uk debut",
  "world tour", "mercury prize",
];

function gigScore(g) {
  let score = 0;

  if (g.editors_pick === true || g.editors_pick === "TRUE") score += 20;
  if (g.special_occasion) score += 8;
  // venue_tier "1" = premier (Vortex, Ronnie's, Barbican etc) = boost
  // venue_tier "2" = good but not top tier (Karamel etc) = no boost
  if (PREMIUM_VENUES.has(g.venue_name)) score += 6;
  if (g.venue_tier === "2") score -= 2;  // demote second-tier venues
  if (g.venue_tier === "3") score -= 5;  // demote third-tier venues (e.g. Karamel)

  const price = parseFloat((g.price_from || '').replace(/[^0-9.]/g, ''));
  if (!isNaN(price)) {
    if (price >= 30) score += 6;
    else if (price >= 20) score += 4;
    else if (price >= 12) score += 2;
    else if (price >= 8)  score += 1;
  }

  if (g.format_tags === 'Concert Hall') score += 3;

  const text = ((g.description || '') + ' ' + (g.artist_name || '')).toLowerCase();
  if (INTERNATIONAL_SIGNALS.some(s => text.includes(s))) score += 5;

  if (g.venue_name === "Ronnie Scott's" && g.stage === 'Main Stage') score += 4;
  if (g.venue_name === 'Vortex Jazz Club') score += 2;

  return score;
}

function sortGigsWithinDay(gigs) {
  return [...gigs].sort((a, b) => {
    const scoreDiff = gigScore(b) - gigScore(a);
    if (scoreDiff !== 0) return scoreDiff;
    return (a.start_time || '').localeCompare(b.start_time || '');
  });
}
