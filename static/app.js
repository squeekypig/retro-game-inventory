// ── State ────────────────────────────────────────────────────────────────────
let sortDir = 'asc';
let ownedFilter = '';
let editingId = null;
let debounceTimer = null;

// ── Platform Badge Colors ────────────────────────────────────────────────────
const PLATFORM_COLORS = {
  'NES':            '#e60012',
  'SNES':           '#7c3aed',
  'N64':            '#009ac7',
  'Nintendo 64':    '#009ac7',
  'Game Boy':       '#6b7280',
  'Game Boy Color': '#ef8014',
  'GBC':            '#ef8014',
  'GBA':            '#7c3aed',
  'Game Boy Advance': '#7c3aed',
  'GameCube':       '#6a0dad',
  'Wii':            '#9ca3af',
  'Wii U':          '#0080d7',
  'DS':             '#e11d48',
  'DS Lite':        '#e11d48',
  '3DS':            '#e11d48',
  'PS1':            '#003087',
  'PlayStation':    '#003087',
  'PS2':            '#003087',
  'PlayStation 2':  '#003087',
  'PS3':            '#003087',
  'PlayStation 3':  '#003087',
  'PS4':            '#003087',
  'PSP':            '#003087',
  'Genesis':        '#1e3a8a',
  'Sega Genesis':   '#1e3a8a',
  'Mega Drive':     '#1e3a8a',
  'Saturn':         '#1565c0',
  'Sega Saturn':    '#1565c0',
  'Dreamcast':      '#ff6f00',
  'Sega Dreamcast': '#ff6f00',
  'Game Gear':      '#0d9488',
  'Master System':  '#1e3a8a',
  'Atari 2600':     '#b45309',
  'Atari 7800':     '#92400e',
  'Atari Lynx':     '#92400e',
  'TurboGrafx-16':  '#be185d',
  'Neo Geo':        '#991b1b',
  'Xbox':           '#16a34a',
  'Xbox 360':       '#16a34a',
};

function getPlatformColor(platform) {
  return PLATFORM_COLORS[platform] || '#4b5563';
}

// ── API Helpers ───────────────────────────────────────────────────────────────
async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ── Load & Render Games ───────────────────────────────────────────────────────
async function loadGames() {
  const search   = document.getElementById('search').value.trim();
  const platform = document.getElementById('platform-filter').value;
  const sort     = document.getElementById('sort-by').value;

  const params = new URLSearchParams({ sort, order: sortDir });
  if (search)   params.set('search', search);
  if (platform) params.set('platform', platform);
  if (ownedFilter) params.set('owned', ownedFilter);

  try {
    const [games, stats] = await Promise.all([
      api('/api/games?' + params),
      api('/api/stats'),
    ]);
    renderGames(games);
    updateStats(stats);
    await loadPlatforms();
  } catch (e) {
    console.error(e);
  }
}

function renderGames(games) {
  const grid = document.getElementById('game-grid');
  const empty = document.getElementById('empty-state');

  if (!games.length) {
    grid.innerHTML = '';
    grid.appendChild(empty);
    return;
  }

  // Count copies by title+platform (case-insensitive) to flag duplicates.
  const copyCounts = {};
  for (const g of games) {
    const key = (g.title + '|' + g.platform).toLowerCase();
    copyCounts[key] = (copyCounts[key] || 0) + 1;
  }

  grid.innerHTML = games.map(g => {
    const copies = copyCounts[(g.title + '|' + g.platform).toLowerCase()];
    const copiesBadge = copies > 1
      ? `<span class="copies-badge" title="${copies} copies in your collection">📦 ×${copies}</span>`
      : '';
    return `
    <div class="game-card" data-id="${g.id}">
      <div class="card-top">
        <span class="platform-badge" style="background:${getPlatformColor(g.platform)}">${esc(g.platform)}</span>
        <div class="card-badges">
          ${copiesBadge}
          <span class="owned-badge ${g.owned ? 'owned' : 'wishlist'}">${g.owned ? '✅ Owned' : '❤️ Wishlist'}</span>
        </div>
      </div>
      <div class="card-title">${esc(g.title)}</div>
      <div class="card-meta">
        ${g.release_year ? `<span>📅 ${g.release_year}</span>` : ''}
        ${g.estimated_value != null ? `<span class="card-value">$${Number(g.estimated_value).toFixed(2)}</span>` : ''}
      </div>
      ${g.notes ? `<div class="card-notes">${esc(g.notes)}</div>` : ''}
      <div class="card-actions">
        <button class="btn-edit" onclick="editGame(${g.id})">✏️ Edit</button>
        <button class="btn-delete" onclick="deleteGame(${g.id}, '${esc(g.title).replace(/'/g, "\\'")}')">🗑️ Delete</button>
      </div>
    </div>`;
  }).join('');
}

function updateStats(stats) {
  document.getElementById('count-owned').textContent    = stats.owned;
  document.getElementById('count-wishlist').textContent = stats.wishlist;
  document.getElementById('count-value').textContent    = '$' + stats.collection_value.toFixed(0);
}

async function loadPlatforms() {
  try {
    const platforms = await api('/api/platforms');
    const sel = document.getElementById('platform-filter');
    const current = sel.value;
    sel.innerHTML = '<option value="">All Platforms</option>' +
      platforms.map(p => `<option value="${esc(p)}" ${p === current ? 'selected' : ''}>${esc(p)}</option>`).join('');
  } catch (_) {}
}

// ── Sort & Filter Controls ────────────────────────────────────────────────────
function toggleSortDir() {
  sortDir = sortDir === 'asc' ? 'desc' : 'asc';
  document.getElementById('sort-dir').textContent = sortDir === 'asc' ? '↑' : '↓';
  loadGames();
}

function setOwnedFilter(btn, value) {
  document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  ownedFilter = value;
  loadGames();
}

function debounceLoad() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadGames, 300);
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function openModal() {
  editingId = null;
  document.getElementById('modal-title').textContent = 'Add Game';
  document.getElementById('modal-tabs').classList.remove('hidden');
  switchTab(document.querySelector('.mtab[data-tab="photo"]'), 'photo');
  clearForm();
  clearPhoto();
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  editingId = null;
}

function overlayClick(e) {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
}

function switchTab(btn, tab) {
  document.querySelectorAll('.mtab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-photo').classList.toggle('hidden', tab !== 'photo');
  document.getElementById('game-form').classList.toggle('hidden', false); // always show form
  if (tab === 'manual') {
    document.getElementById('tab-photo').classList.add('hidden');
  } else {
    document.getElementById('tab-photo').classList.remove('hidden');
  }
}

// ── Photo Upload & Identification ─────────────────────────────────────────────
function handleDrop(e) {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) showPreview(file);
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) showPreview(file);
}

function showPreview(file) {
  const reader = new FileReader();
  reader.onload = ev => {
    const preview = document.getElementById('photo-preview');
    preview.src = ev.target.result;
    preview.classList.remove('hidden');
    document.getElementById('drop-zone').classList.add('hidden');
    document.getElementById('identify-actions').classList.remove('hidden');
    document.getElementById('identify-loading').classList.add('hidden');
    document.getElementById('identify-result').classList.add('hidden');
    // Store file reference
    preview._file = file;
  };
  reader.readAsDataURL(file);
}

function clearPhoto() {
  const preview = document.getElementById('photo-preview');
  preview.classList.add('hidden');
  preview.src = '';
  preview._file = null;
  document.getElementById('photo-input').value = '';
  document.getElementById('drop-zone').classList.remove('hidden');
  document.getElementById('identify-actions').classList.add('hidden');
  document.getElementById('identify-loading').classList.add('hidden');
  document.getElementById('identify-result').classList.add('hidden');
  resetDupWarning();
}

function compressImage(file) {
  return new Promise(resolve => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const MAX = 1600;
      let { width, height } = img;
      if (width > MAX || height > MAX) {
        const ratio = Math.min(MAX / width, MAX / height);
        width = Math.round(width * ratio);
        height = Math.round(height * ratio);
      }
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      canvas.getContext('2d').drawImage(img, 0, 0, width, height);
      canvas.toBlob(blob => resolve(new File([blob], 'photo.jpg', { type: 'image/jpeg' })),
        'image/jpeg', 0.88);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}

async function checkForDuplicates(title, platform) {
  if (!title || !platform) { resetDupWarning(); return; }
  let res;
  try {
    res = await api('/api/duplicate-check?' + new URLSearchParams({ title, platform }));
  } catch (_) {
    resetDupWarning();
    return;
  }
  if (!res.count) { resetDupWarning(); return; }

  let detail;
  if (res.owned > 0) {
    detail = `you own ${res.owned} cop${res.owned === 1 ? 'y' : 'ies'}`;
    if (res.wishlist > 0) detail += ` and have ${res.wishlist} on your wishlist`;
  } else {
    detail = `this is on your wishlist (${res.wishlist})`;
  }

  const warn = document.getElementById('dup-warning');
  warn.innerHTML =
    `<strong>⚠️ Already in your collection</strong>` +
    `<span>${esc(title)} (${esc(platform)}) — ${detail}. Saving will add another copy.</span>`;
  warn.classList.remove('hidden');
  document.getElementById('save-btn').textContent = '➕ Add Another Copy';
}

function resetDupWarning() {
  const warn = document.getElementById('dup-warning');
  warn.classList.add('hidden');
  warn.innerHTML = '';
  document.getElementById('save-btn').textContent = 'Save Game';
}

async function identifyGame() {
  const preview = document.getElementById('photo-preview');
  const file = preview._file;
  if (!file) return;

  document.getElementById('identify-actions').classList.add('hidden');
  document.getElementById('identify-loading').classList.remove('hidden');
  document.getElementById('identify-result').classList.add('hidden');

  try {
    const compressed = await compressImage(file);
    const formData = new FormData();
    formData.append('file', compressed, 'photo.jpg');
    const result = await fetch('/api/identify', { method: 'POST', body: formData })
      .then(async r => {
        if (!r.ok) {
          const detail = await r.json().catch(() => ({}));
          throw new Error(detail.detail || `Server error ${r.status}`);
        }
        return r.json();
      });

    // Populate form
    setField('f-title',    result.title    || '');
    setField('f-platform', result.platform || '');
    setField('f-year',     result.release_year || '');

    // Show confidence
    const badge = document.getElementById('confidence-badge');
    const confClass = { high: 'conf-high', medium: 'conf-medium', low: 'conf-low' }[result.confidence] || 'conf-low';
    badge.className = `confidence-badge ${confClass}`;
    badge.textContent = { high: '✅ High confidence', medium: '⚠️ Medium confidence', low: '❓ Low confidence' }[result.confidence] || 'Unknown';

    const notesEl = document.getElementById('identify-notes');
    if (result.notes) {
      notesEl.textContent = result.notes;
      notesEl.classList.remove('hidden');
    } else {
      notesEl.classList.add('hidden');
    }

    document.getElementById('identify-result').classList.remove('hidden');
    checkForDuplicates(result.title, result.platform);
  } catch (e) {
    alert('Could not identify game: ' + e.message);
  } finally {
    document.getElementById('identify-loading').classList.add('hidden');
    document.getElementById('identify-actions').classList.remove('hidden');
  }
}

// ── Form Helpers ──────────────────────────────────────────────────────────────
function setField(id, value) {
  document.getElementById(id).value = value ?? '';
}

function getField(id) {
  return document.getElementById(id).value.trim();
}

function clearForm() {
  ['f-title', 'f-platform', 'f-year', 'f-value', 'f-notes'].forEach(id => setField(id, ''));
  setStatus(document.querySelector('.status-btn[data-owned="true"]'));
}

function setStatus(btn) {
  document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

function getOwnedStatus() {
  const active = document.querySelector('.status-btn.active');
  return active ? active.dataset.owned === 'true' : true;
}

// ── Save Game ─────────────────────────────────────────────────────────────────
async function saveGame() {
  const title    = getField('f-title');
  const platform = getField('f-platform');
  if (!title)    { alert('Title is required'); return; }
  if (!platform) { alert('Platform is required'); return; }

  const payload = {
    title,
    platform,
    release_year:    getField('f-year')  ? parseInt(getField('f-year'))   : null,
    estimated_value: getField('f-value') ? parseFloat(getField('f-value')): null,
    owned:  getOwnedStatus(),
    notes:  getField('f-notes') || null,
  };

  const btn = document.getElementById('save-btn');
  btn.disabled = true;
  btn.textContent = 'Saving…';

  try {
    if (editingId) {
      await api(`/api/games/${editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      await api('/api/games', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }
    closeModal();
    loadGames();
  } catch (e) {
    alert('Failed to save: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Game';
  }
}

// ── Edit & Delete ─────────────────────────────────────────────────────────────
async function editGame(id) {
  try {
    const g = await api(`/api/games/${id}`);
    editingId = id;
    resetDupWarning();
    document.getElementById('modal-title').textContent = 'Edit Game';
    document.getElementById('modal-tabs').classList.add('hidden');
    document.getElementById('tab-photo').classList.add('hidden');

    setField('f-title',    g.title);
    setField('f-platform', g.platform);
    setField('f-year',     g.release_year   || '');
    setField('f-value',    g.estimated_value != null ? g.estimated_value : '');
    setField('f-notes',    g.notes          || '');

    const statusBtn = document.querySelector(`.status-btn[data-owned="${g.owned}"]`);
    if (statusBtn) setStatus(statusBtn);

    document.getElementById('modal-overlay').classList.remove('hidden');
  } catch (e) {
    alert('Could not load game: ' + e.message);
  }
}

async function deleteGame(id, title) {
  if (!confirm(`Delete "${title}" from your collection?`)) return;
  try {
    await api(`/api/games/${id}`, { method: 'DELETE' });
    loadGames();
  } catch (e) {
    alert('Delete failed: ' + e.message);
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Value Lookup ──────────────────────────────────────────────────────────────
async function lookupValue() {
  const title = getField('f-title');
  const platform = getField('f-platform');
  if (!title || !platform) {
    alert('Enter a title and platform first.');
    return;
  }
  const btn = document.getElementById('lookup-btn');
  const info = document.getElementById('value-info');
  btn.textContent = '…';
  btn.disabled = true;
  info.classList.add('hidden');
  try {
    const result = await api('/api/lookup-value', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, platform }),
    });
    if (result.loose != null) {
      setField('f-value', result.loose.toFixed(2));
    }
    const parts = [];
    if (result.cib != null) parts.push(`CIB $${result.cib.toFixed(2)}`);
    if (result.notes) parts.push(result.notes);
    if (parts.length) {
      info.textContent = parts.join(' · ');
      info.classList.remove('hidden');
    }
  } catch (e) {
    alert('Could not look up value: ' + e.message);
  } finally {
    btn.textContent = 'Look up';
    btn.disabled = false;
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
if (navigator.maxTouchPoints > 0) {
  document.getElementById('drop-icon').textContent = '📷';
  document.getElementById('drop-main').textContent = 'Tap to take a photo';
  document.getElementById('drop-sub').textContent = 'Or choose from your library';
}
loadGames();
