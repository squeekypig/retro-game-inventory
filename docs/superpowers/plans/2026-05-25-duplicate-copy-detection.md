# Duplicate-Copy Detection & Multi-Copy Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a user scans a game already in the collection, warn them (without blocking) and let them add a second copy, and show a `×N` badge on cards that have duplicates.

**Architecture:** A new read-only backend endpoint counts existing rows matching a title+platform (case-insensitive, any owned/wishlist status). The photo-scan flow calls it after identification and shows an informational banner; the collection grid groups loaded games client-side and badges any card belonging to a group of 2+. Copies remain separate rows (no schema change); a "copy" is just another `POST /api/games`.

**Tech Stack:** FastAPI + SQLite (backend), vanilla JS + static HTML/CSS (frontend). No JS test runner exists; backend gets an automated urllib test (matching `test_add_game.py`), frontend is verified by running the app.

**Preconditions for all tasks:** The dev server is running via `start.bat` (uvicorn on `http://127.0.0.1:8000` with `--reload`), so backend/static changes are picked up automatically. Work happens on branch `feature/duplicate-copy-detection`.

---

## File Structure

- `main.py` — add one route, `GET /api/duplicate-check` (Task 1). No other backend changes.
- `test_duplicate_check.py` (new) — automated endpoint test (Task 1).
- `static/index.html` — add the hidden `#dup-warning` banner element (Task 2).
- `static/app.js` — duplicate-check call + banner render/reset + Save relabel (Task 2); grid grouping + `×N` badge (Task 3).
- `static/style.css` — `.dup-warning` styles (Task 2); `.copies-badge` + `.card-badges` styles (Task 3).

---

### Task 1: Backend `/api/duplicate-check` endpoint

**Files:**
- Create: `test_duplicate_check.py`
- Modify: `main.py` (add route after the `get_stats` function, before the `@app.post("/api/lookup-value")` decorator)

- [ ] **Step 1: Write the failing test**

Create `test_duplicate_check.py`:

```python
"""Test /api/duplicate-check: counts existing copies by title+platform.

Creates throwaway rows against the running dev server and deletes them again,
so the real collection is left unchanged.
"""
import json
import urllib.error
import urllib.request
from urllib.parse import urlencode

BASE = "http://127.0.0.1:8000"
TITLE, PLATFORM = "ZZ Test Cart 9000", "NES"


def post_game(title, platform, owned=True):
    data = json.dumps({"title": title, "platform": platform, "owned": owned}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/games", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["id"]


def delete_game(gid):
    req = urllib.request.Request(f"{BASE}/api/games/{gid}", method="DELETE")
    with urllib.request.urlopen(req) as r:
        r.read()


def dup_check(title, platform):
    q = urlencode({"title": title, "platform": platform})
    with urllib.request.urlopen(f"{BASE}/api/duplicate-check?{q}") as r:
        return json.loads(r.read())


created = []
try:
    base = dup_check(TITLE, PLATFORM)
    assert base["count"] == 0, f"expected clean baseline, got {base}"

    created.append(post_game(TITLE, PLATFORM, owned=True))
    created.append(post_game(TITLE, PLATFORM, owned=False))  # wishlist copy

    res = dup_check(TITLE, PLATFORM)
    assert res["count"] == 2, res
    assert res["owned"] == 1, res
    assert res["wishlist"] == 1, res

    ci = dup_check(TITLE.lower(), "nes")          # case-insensitive
    assert ci["count"] == 2, ci

    diff = dup_check(TITLE, "SNES")               # different platform
    assert diff["count"] == 0, diff

    print("PASS: duplicate-check returns correct counts")
finally:
    for gid in created:
        delete_game(gid)
    print(f"cleaned up {len(created)} test rows")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python test_duplicate_check.py`
Expected: FAIL — raises `urllib.error.HTTPError: HTTP Error 404: Not Found` on the first `dup_check` call (the route does not exist yet; the static-file mount returns 404).

- [ ] **Step 3: Write minimal implementation**

In `main.py`, add this route immediately after the `get_stats` function's `return` line and before the `@app.post("/api/lookup-value")` decorator:

```python
@app.get("/api/duplicate-check")
def duplicate_check(title: str, platform: str):
    conn = get_db()
    rows = conn.execute(
        "SELECT owned FROM games "
        "WHERE title = ? COLLATE NOCASE AND platform = ? COLLATE NOCASE",
        (title, platform),
    ).fetchall()
    conn.close()
    owned = sum(1 for r in rows if r["owned"])
    return {"count": len(rows), "owned": owned, "wishlist": len(rows) - owned}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python test_duplicate_check.py`
Expected: PASS — prints `PASS: duplicate-check returns correct counts` then `cleaned up 2 test rows`. (If it fails because the server hasn't reloaded, wait for uvicorn's reload log line and re-run.)

- [ ] **Step 5: Commit**

```bash
git add main.py test_duplicate_check.py
git commit -m "feat: add /api/duplicate-check endpoint

Counts existing rows matching a title+platform (case-insensitive, any
owned/wishlist status) so the UI can flag duplicate scans.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Scan-time duplicate banner

**Files:**
- Modify: `static/index.html` (insert banner element before `<div id="game-form" ...>`)
- Modify: `static/style.css` (append `.dup-warning` styles)
- Modify: `static/app.js` (add `checkForDuplicates` + `resetDupWarning`; call from `identifyGame`; reset from `clearPhoto` and `editGame`)

- [ ] **Step 1: Add the banner element to the modal**

In `static/index.html`, find the end of the photo tab and the start of the shared form:

```html
        <div id="identify-result" class="identify-result hidden">
          <div class="confidence-badge" id="confidence-badge"></div>
          <p id="identify-notes" class="identify-notes hidden"></p>
        </div>
      </div>

      <!-- Form (shared between photo and manual tabs) -->
      <div id="game-form" class="game-form">
```

Insert the banner between the closing `</div>` of `#tab-photo` and the `<!-- Form ... -->` comment, so the block reads:

```html
        <div id="identify-result" class="identify-result hidden">
          <div class="confidence-badge" id="confidence-badge"></div>
          <p id="identify-notes" class="identify-notes hidden"></p>
        </div>
      </div>

      <!-- Duplicate-copy warning (shown after identifying a game already in the collection) -->
      <div id="dup-warning" class="dup-warning hidden"></div>

      <!-- Form (shared between photo and manual tabs) -->
      <div id="game-form" class="game-form">
```

- [ ] **Step 2: Add banner styles**

Append to the end of `static/style.css`:

```css
/* ── Duplicate-copy warning ─────────────────────── */
.dup-warning {
  background: rgba(245, 158, 11, .12);
  border: 1px solid var(--yellow);
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 0.82rem;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.dup-warning strong { color: var(--yellow); font-size: 0.85rem; }
.dup-warning span { color: var(--muted); }
.dup-warning.hidden { display: none; }
```

- [ ] **Step 3: Add the duplicate-check + reset functions to app.js**

In `static/app.js`, add these two functions in the "Photo Upload & Identification" section (e.g. directly above `async function identifyGame()`):

```js
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
```

- [ ] **Step 4: Call the check after identification**

In `identifyGame()`, find the line that reveals the result:

```js
    document.getElementById('identify-result').classList.remove('hidden');
```

Add this line immediately after it (still inside the `try`):

```js
    checkForDuplicates(result.title, result.platform);
```

- [ ] **Step 5: Reset the banner when the form is cleared or reused**

In `clearPhoto()`, find the last line before its closing brace:

```js
  document.getElementById('identify-result').classList.add('hidden');
```

Add immediately after it:

```js
  resetDupWarning();
```

Then in `editGame(id)`, find:

```js
    editingId = id;
    document.getElementById('modal-title').textContent = 'Edit Game';
```

Add `resetDupWarning();` immediately after `editingId = id;`, so a stale banner never carries into edit mode:

```js
    editingId = id;
    resetDupWarning();
    document.getElementById('modal-title').textContent = 'Edit Game';
```

(`openModal()` already calls `clearPhoto()`, so it is covered by the reset above.)

- [ ] **Step 6: Manual verification**

1. Hard-refresh `http://localhost:8000` (Ctrl+F5).
2. Pick any game already in your collection. Click **+ Add Game**, upload/scan a photo of it, click **Identify Game**.
3. Confirm: the yellow banner appears above the form reading "⚠️ Already in your collection — <title> (<platform>) — you own N cop(y/ies)…", and the Save button now reads **➕ Add Another Copy**.
4. Click **Cancel**, reopen **+ Add Game**, and confirm the banner is gone and the button reads **Save Game** again.
5. Scan a game NOT in your collection and confirm no banner appears.

- [ ] **Step 7: Commit**

```bash
git add static/index.html static/style.css static/app.js
git commit -m "feat: warn when scanning a game already in the collection

After identifying a photo, check title+platform against the collection
and show a non-blocking banner; relabel Save to 'Add Another Copy'.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Multi-copy `×N` badge on the grid

**Files:**
- Modify: `static/app.js` (`renderGames` — group by title+platform, add badge)
- Modify: `static/style.css` (append `.copies-badge` + `.card-badges` styles)

- [ ] **Step 1: Replace the `renderGames` body with a grouped version**

In `static/app.js`, replace the entire `renderGames` function with:

```js
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
```

- [ ] **Step 2: Add badge styles**

Append to the end of `static/style.css`:

```css
/* ── Multi-copy badge ───────────────────────────── */
.card-badges { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.copies-badge {
  font-size: 0.72rem;
  padding: 3px 8px;
  border-radius: 20px;
  font-weight: 700;
  background: var(--accent-dim);
  color: #c4b5fd;
  white-space: nowrap;
}
```

- [ ] **Step 3: Manual verification**

1. Hard-refresh `http://localhost:8000` (Ctrl+F5).
2. Ensure at least one game has 2+ copies (use the Task 2 flow to add a second copy of something, or add two manually with the same title + platform).
3. Confirm: both cards for that game show a `📦 ×2` purple badge in the header, next to the Owned/Wishlist badge; the platform badge stays on the left.
4. Confirm: games with a single copy show no badge and look unchanged.
5. Delete one of the two copies and confirm the badge disappears from the remaining card after the grid refreshes.

- [ ] **Step 4: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: show a copies badge on cards with duplicates

renderGames groups the loaded games by title+platform and badges every
card in a group of 2+ with the copy count.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- `/api/duplicate-check` endpoint (counts, case-insensitive, any status) → Task 1 ✓
- Scan-time banner above the form, status-aware wording → Task 2 ✓
- Save relabel to "➕ Add Another Copy" → Task 2 (Step 3) ✓
- Reset banner on modal open / photo clear → Task 2 (Step 5; `openModal`→`clearPhoto`, plus `editGame`) ✓
- Separate cards with `×N` badge, computed from loaded list → Task 3 ✓
- Scope = scan flow only; manual entry shows no banner → satisfied (check only called from `identifyGame`) ✓
- Backend urllib test (counts, case-insensitivity, different platform = 0) → Task 1 ✓

**Placeholder scan:** No TBD/TODO; every code/command step has concrete content. ✓

**Type/name consistency:** `checkForDuplicates`/`resetDupWarning` referenced consistently; endpoint returns `{count, owned, wishlist}` and the banner reads exactly those keys; `#dup-warning`, `#save-btn`, `.copies-badge`, `.card-badges` used consistently across HTML/CSS/JS. ✓
