# Mobile Fix (no-cache static assets + mobile pass) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make UI updates reliably reach mobile browsers (fixing the `×N` badge that "didn't appear" on a phone due to stale cached assets) and tighten the phone experience.

**Architecture:** Serve static files through a `StaticFiles` subclass that adds `Cache-Control: no-cache`, so browsers revalidate every load (cheap `304`s via the existing ETag) and pick up changes immediately. Add a CSS-only mobile pass: wrap the card header defensively and enlarge touch targets / fit the modal on phones.

**Tech Stack:** FastAPI + Starlette `StaticFiles` (backend), vanilla CSS (frontend). Backend gets an automated urllib header test; the CSS pass is verified visually on a phone.

**Preconditions:** Dev server running via `start.bat` (uvicorn on `http://127.0.0.1:8000`, `--reload`). Work on branch `feature/duplicate-copy-detection` (this folds into the open PR #1).

---

## File Structure

- `main.py` — define `NoCacheStaticFiles(StaticFiles)` and use it in the existing `/` mount (Task 1). No other backend logic changes.
- `test_cache_headers.py` (new) — asserts static assets send `Cache-Control: no-cache` (Task 1).
- `static/style.css` — `.card-top` gets `flex-wrap: wrap`; the existing `@media (max-width: 640px)` block gains touch-target / modal / form-split rules (Task 2).

---

### Task 1: Serve static assets with `Cache-Control: no-cache`

**Files:**
- Create: `test_cache_headers.py`
- Modify: `main.py` (the static-mount block at the end of the file)

- [ ] **Step 1: Write the failing test**

Create `test_cache_headers.py`:

```python
"""Static assets must be served with Cache-Control: no-cache so browsers
revalidate and never serve a stale build (e.g. on mobile)."""
import urllib.request

BASE = "http://127.0.0.1:8000"


def cache_control(path):
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return r.headers.get("Cache-Control")


for path in ("/app.js", "/style.css"):
    cc = cache_control(path)
    assert cc == "no-cache", f"{path}: expected 'no-cache', got {cc!r}"
    print(f"OK {path}: Cache-Control: {cc}")

print("PASS: static assets send Cache-Control: no-cache")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python test_cache_headers.py`
Expected: FAIL — `AssertionError: /app.js: expected 'no-cache', got None` (the plain mount sends no `Cache-Control`).

- [ ] **Step 3: Write minimal implementation**

In `main.py`, find the static-mount block at the end of the file:

```python
# Serve static files last so API routes take precedence
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True))
```

Replace it with (define the subclass, then mount it):

```python
class NoCacheStaticFiles(StaticFiles):
    """Serve static files with Cache-Control: no-cache so browsers always
    revalidate (cheap 304s via ETag) and pick up updates immediately, instead
    of serving stale JS/CSS heuristically cached from an older build."""
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Serve static files last so API routes take precedence
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", NoCacheStaticFiles(directory=str(STATIC_DIR), html=True))
```

(`StaticFiles` is already imported at the top via `from fastapi.staticfiles import StaticFiles`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python test_cache_headers.py`
Expected: PASS — prints `OK /app.js: Cache-Control: no-cache`, `OK /style.css: Cache-Control: no-cache`, then `PASS: ...`. (If it still fails, wait for uvicorn's reload log line and re-run.)

- [ ] **Step 5: Commit**

```bash
git add main.py test_cache_headers.py
git commit -m "fix: serve static assets with Cache-Control: no-cache

Without it, browsers heuristically cached app.js/style.css and served
stale builds (the copies badge never reached mobile). no-cache forces
revalidation; unchanged files still return 304 via the existing ETag.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Focused mobile CSS pass

**Files:**
- Modify: `static/style.css` (the `.card-top` rule, and the `@media (max-width: 640px)` block)

- [ ] **Step 1: Make the card header wrap (defensive, all viewports)**

In `static/style.css`, find the `.card-top` rule:

```css
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
```

Replace it with (adds `flex-wrap: wrap;`):

```css
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 8px;
}
```

- [ ] **Step 2: Extend the mobile media query**

In `static/style.css`, find the existing responsive block:

```css
@media (max-width: 640px) {
  header { flex-wrap: wrap; }
  .header-stats { order: 3; width: 100%; justify-content: flex-start; }
  .controls { gap: 8px; }
  main { padding: 16px; gap: 12px; }
}
```

Replace it with (keeps the existing four rules, appends the new ones):

```css
@media (max-width: 640px) {
  header { flex-wrap: wrap; }
  .header-stats { order: 3; width: 100%; justify-content: flex-start; }
  .controls { gap: 8px; }
  main { padding: 16px; gap: 12px; }

  /* Larger touch targets (~44px) */
  .card-actions button { padding: 10px; }
  .filter-tab { padding: 9px 14px; }
  .sort-dir { width: 40px; height: 40px; }
  .mtab { padding: 11px 16px; }

  /* Modal fits small screens */
  .modal { padding: 16px; max-height: 95vh; }

  /* Stack Year / Est. Value */
  .form-row-split { grid-template-columns: 1fr; }
}
```

- [ ] **Step 3: Verify the rules are in place**

Run (Bash): `grep -n "flex-wrap: wrap" static/style.css && grep -n "max-height: 95vh\|grid-template-columns: 1fr" static/style.css`
Expected: shows `flex-wrap: wrap;` inside `.card-top`, plus the `.modal` and `.form-row-split` mobile overrides. Then confirm the running server serves the updated CSS: `curl -s http://127.0.0.1:8000/style.css | grep -c "max-height: 95vh"` → `1`.
Note: final visual confirmation on a phone (after clearing site data once) is deferred to the human.

- [ ] **Step 4: Commit**

```bash
git add static/style.css
git commit -m "feat: focused mobile CSS pass

Wrap the card header so badges never overflow on narrow cards; on phones
enlarge tap targets, fit the modal, and stack the year/value form split.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- `Cache-Control: no-cache` via `StaticFiles` subclass → Task 1 ✓
- Backend test asserting the header → Task 1 (`test_cache_headers.py`) ✓
- `.card-top` wrap (defensive) → Task 2 Step 1 ✓
- Mobile tap targets / modal / form-split → Task 2 Step 2 ✓
- Scope: CSS-only pass, no redesign, no new deps → respected ✓
- One-time cache-clear caveat → operational note for the human (below), not a code task ✓

**Placeholder scan:** No TBD/TODO; every step has concrete code or an exact command. ✓

**Type/name consistency:** `NoCacheStaticFiles` defined and used in the same task; test reads `Cache-Control`, implementation sets `Cache-Control`; CSS selectors (`.card-top`, `.card-actions button`, `.filter-tab`, `.sort-dir`, `.mtab`, `.modal`, `.form-row-split`) all exist in the current stylesheet. ✓

## Operational note (after merge/deploy)

The phone still holds the old assets cached *without* `Cache-Control`. The user must clear site data / load once in a private tab to get the updated build; `no-cache` keeps it fresh from then on.
