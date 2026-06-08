/**
 * data.js — fetches JSON data files from GitHub
 * Update GITHUB_USER and GITHUB_REPO to match your repo
 */

const GITHUB_USER = 'ianlathamvortex';
const GITHUB_REPO = 'london_jazz_listings';
const BRANCH      = 'main';

const RAW = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/${BRANCH}/data`;

const URLS = {
  gigs:         `${RAW}/gigs.json`,
  jam_sessions: `${RAW}/jam_sessions.json`,
  brunches:     `${RAW}/brunches.json`,
  free_entry:   `${RAW}/free_entry.json`,
  festivals:    `${RAW}/festivals.json`,
};

// Simple in-memory cache
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

// ── Helpers ──────────────────────────────────────────────────

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

function dayOfWeek(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-GB', { weekday: 'long' });
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

function nextNDays(n) {
  const dates = [];
  const d = new Date();
  for (let i = 0; i < n; i++) {
    dates.push(d.toISOString().slice(0, 10));
    d.setDate(d.getDate() + 1);
  }
  return dates;
}

// Group gigs by date
function groupByDate(gigs) {
  const groups = {};
  for (const g of gigs) {
    if (!groups[g.date]) groups[g.date] = [];
    groups[g.date].push(g);
  }
  return groups;
}

// Get unique values of a field from an array
function uniqueValues(arr, field) {
  const vals = arr
    .map(x => x[field])
    .filter(Boolean)
    .flatMap(v => v.includes(',') ? v.split(',').map(s => s.trim()) : [v]);
  return [...new Set(vals)].sort();
}

// Get upcoming dates from gig data
function upcomingDates(gigs, n = 14) {
  const t = today();
  return [...new Set(
    gigs
      .map(g => g.date)
      .filter(d => d >= t)
      .sort()
  )].slice(0, n);
}
