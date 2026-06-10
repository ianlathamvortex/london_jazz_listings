/**
 * utils.js — shared UI helpers
 */

// ── Header component ─────────────────────────────────────────

function renderHeader(activePage) {
  const nav = [
    { href: 'index.html',     label: 'Home' },
    { href: 'gigs.html',      label: 'Gigs' },
    { href: 'jams.html',      label: 'Jam Sessions' },
    { href: 'brunches.html',  label: 'Brunches' },
    { href: 'free.html',      label: 'Free Entry' },
    { href: 'festivals.html', label: 'Festivals' },
    { href: 'dining.html',    label: 'Dining' },
  ];

  const navHtml = nav.map(n =>
    `<a href="${n.href}" class="${activePage === n.href ? 'active' : ''}">${n.label}</a>`
  ).join('');

  const dateStr = new Date().toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  });

  return `
    <header class="site-header">
      <div class="container">
        <div class="header-top">
          <div>
            <div class="site-title"><a href="index.html">The London Jazz List</a></div>
            <div class="site-tagline">London's jazz gigs, jams &amp; brunches</div>
          </div>
          <div class="header-date">${dateStr}</div>
        </div>
        <nav class="site-nav">${navHtml}</nav>
      </div>
    </header>`;
}

// ── Footer component ─────────────────────────────────────────

function renderFooter() {
  return `
    <footer class="site-footer">
      <div class="container">
        <div class="footer-inner">
          <div class="footer-brand">The London Jazz List</div>
          <div class="footer-links">
            <a href="index.html">Home</a>
            <a href="gigs.html">Gigs</a>
            <a href="jams.html">Jams</a>
          </div>
          <p class="footer-note">
            Updated nightly. Listings sourced automatically from venue websites.
            Missing a gig? Email us.
          </p>
        </div>
      </div>
    </footer>`;
}

// ── Gig card ─────────────────────────────────────────────────

function renderGigCard(gig) {
  const isEditorsPick = gig.editors_pick === true || gig.editors_pick === 'TRUE';
  const tags = [];

  if (gig.special_occasion) tags.push(`<span class="tag tag-special">${esc(gig.special_occasion)}</span>`);
  if (gig.genre_tier1) tags.push(`<span class="tag">${esc(gig.genre_tier1)}</span>`);
  if (gig.format_tags) tags.push(`<span class="tag">${esc(gig.format_tags)}</span>`);
  if (gig.price_from === 'Free' || gig.price_from?.toLowerCase() === 'free') tags.push(`<span class="tag tag-free">Free</span>`);

  const priceStr = gig.price_full_text || gig.price_from || '';
  // Never show 'Free' unless explicitly set — empty price means unknown, not free
  const timeStr  = gig.start_time || '';
  const desc     = gig.description || '';
  const stage    = gig.stage ? ` · ${esc(gig.stage)}` : '';

  const ticketBtn = gig.ticket_url
    ? `<a href="${esc(gig.ticket_url)}" target="_blank" rel="noopener" class="gig-ticket-link">Book →</a>`
    : '';

  return `
    <div class="gig-card ${isEditorsPick ? 'editors-pick' : ''}">
      <div class="gig-main">
        <div class="gig-artist">${esc(gig.artist_name)}</div>
        <div class="gig-venue">
          <span class="gig-venue-name">${esc(gig.venue_name)}</span>${stage}
          ${gig.neighbourhood ? ` · <span>${esc(gig.neighbourhood)}</span>` : ''}
        </div>
        ${desc ? `<div class="gig-description">${esc(desc)}</div>` : ''}
        ${tags.length ? `<div class="gig-tags">${tags.join('')}</div>` : ''}
      </div>
      <div class="gig-aside">
        ${timeStr ? `<div class="gig-time">${esc(timeStr)}</div>` : ''}
        ${priceStr ? `<div class="gig-price">${esc(priceStr)}</div>` : ''}
        ${ticketBtn}
      </div>
    </div>`;
}

// ── Jam session card ─────────────────────────────────────────

function renderJamCard(jam) {
  const isEditorsPick = jam.editors_pick === true || jam.editors_pick === 'TRUE';
  const price = jam.price_notes || (jam.free_or_paid === 'Free' ? 'Free entry' : jam.free_or_paid) || '';
  const sitIn = jam.open_to_sit_in ? 'Open sit-in' : '';
  const websiteUrl = jam.website || '';
  const nameHtml = websiteUrl
    ? `<a href="${esc(websiteUrl)}" target="_blank" rel="noopener noreferrer" class="jam-name-link">${esc(jam.session_name)}</a>`
    : esc(jam.session_name);

  return `
    <div class="jam-card ${isEditorsPick ? 'jam-editors-pick' : ''}">
      <div class="jam-day">${esc(jam.day_of_week || '')} · ${esc(jam.start_time || '')}${jam.end_time ? '–' + esc(jam.end_time) : ''}</div>
      <div class="jam-name">${nameHtml}</div>
      <div class="jam-venue">${esc(jam.venue_name)}${jam.neighbourhood ? ` · ${esc(jam.neighbourhood)}` : ''}</div>
      <div class="jam-details">
        ${jam.host_musician ? `<span>Host: ${esc(jam.host_musician)}</span>` : ''}
        ${price ? `<span>${esc(price)}</span>` : ''}
        ${sitIn ? `<span>${sitIn}</span>` : ''}
      </div>
      ${jam.session_story ? `<div class="jam-story">${esc(jam.session_story)}</div>` : ''}
    </div>`;
}

// ── Brunch card ───────────────────────────────────────────────

function renderBrunchCard(brunch) {
  const when = [brunch.day_of_week, brunch.start_time, brunch.end_time]
    .filter(Boolean).join(' · ');
  const flags = [];
  if (brunch.food_served === true || brunch.food_served === 'TRUE') flags.push('Food served');
  if (brunch.family_friendly === true || brunch.family_friendly === 'TRUE') flags.push('Family friendly');
  if (brunch.reservation_required === true || brunch.reservation_required === 'TRUE') flags.push('Booking required');

  return `
    <div class="brunch-card">
      <div class="brunch-venue">${esc(brunch.venue_name)}</div>
      <div class="brunch-when">${esc(when)}${brunch.neighbourhood ? ` · ${esc(brunch.neighbourhood)}` : ''}</div>
      ${brunch.description ? `<div class="brunch-desc">${esc(brunch.description)}</div>` : ''}
      <div class="brunch-meta">
        ${esc(brunch.price_type || brunch.price_notes || '')}
        ${flags.map(f => `<span>· ${f}</span>`).join('')}
      </div>
    </div>`;
}

// ── Free entry item ───────────────────────────────────────────

function renderFreeItem(item) {
  const dateStr = item.date ? formatDateShort(item.date) : (item.frequency || 'Recurring');
  const timeStr = item.start_time ? ` · ${esc(item.start_time)}` : '';
  const endStr  = item.end_time   ? `–${esc(item.end_time)}`   : '';
  const link    = item.booking_url || item.source_url || '';
  const nameHtml = link
    ? `<a href="${esc(link)}" target="_blank" rel="noopener" class="free-name-link">${esc(item.event_name || item.artist_name || '')}</a>`
    : `<span>${esc(item.event_name || item.artist_name || '')}</span>`;
  return `
    <div class="free-item">
      <div class="free-date">${esc(dateStr)}${timeStr}${endStr}</div>
      <div>
        <div class="free-name">${nameHtml}</div>
        <div class="free-venue">${esc(item.venue_name || '')}${item.neighbourhood ? ` · ${esc(item.neighbourhood)}` : ''}</div>
        ${item.description ? `<div class="free-desc">${esc(item.description)}</div>` : ''}
      </div>
      <div><span class="free-badge">Free</span></div>
    </div>`;
}

// ── Escape HTML ───────────────────────────────────────────────

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ── Loading / empty states ────────────────────────────────────

function showLoading(el) {
  el.innerHTML = '<div class="loading">Loading</div>';
}

function showEmpty(el, msg = 'No listings found.') {
  el.innerHTML = `<div class="empty-state"><p>${msg}</p></div>`;
}

// ── Active nav ────────────────────────────────────────────────

function setActiveNav() {
  const page = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.site-nav a').forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === page);
  });
}

// ── Dining card ───────────────────────────────────────────────

function renderDiningCard(d) {
  const isEditorsPick = d.editors_pick === true || d.editors_pick === 'TRUE';
  const price = d.price_notes || d.price_type || '';
  const days = d.days_of_week || d.frequency || '';
  const booking = d.reservation_required ? 'Booking required' : 'Walk-ins welcome';

  return `
    <div class="brunch-card ${isEditorsPick ? 'editors-pick' : ''}">
      <div class="brunch-venue">${isEditorsPick ? '★ ' : ''}${esc(d.venue_name)}</div>
      <div class="brunch-when">${esc(days)}${d.neighbourhood ? ` · ${esc(d.neighbourhood)}` : ''}</div>
      <div class="brunch-when" style="font-style:normal">${esc(d.music_notes || '')}</div>
      ${d.description ? `<div class="brunch-desc">${esc(d.description)}</div>` : ''}
      <div class="brunch-meta">
        ${esc(price)}
        <span>· ${booking}</span>
        ${d.website ? `· <a href="${esc(d.website)}" target="_blank" rel="noopener" style="border-bottom:1px solid currentColor">Website</a>` : ''}
      </div>
    </div>`;
}
