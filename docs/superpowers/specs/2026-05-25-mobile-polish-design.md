# Mobile fix: stale static assets + focused mobile pass

- **Date:** 2026-05-25
- **Status:** Approved (design)
- **Component:** RetroVault — static asset serving + responsive CSS
- **Branch:** continues on `feature/duplicate-copy-detection` (folds into the open PR #1, since it makes that feature actually reach mobile)

## Goal

Make UI updates reliably reach mobile browsers, and tighten the phone
experience. The trigger was the new `×N` copies badge "not appearing" on a
phone.

## Root cause (confirmed)

Static files are served with `ETag`/`Last-Modified` but **no `Cache-Control`
header**, and `index.html` references `app.js`/`style.css` with no version
string. Browsers then apply *heuristic caching* and serve stale copies without
revalidating. The phone was holding pre-feature `app.js`/`style.css`, so the
badge (and the duplicate banner) never reached it. Confirmed: in a private tab
on the phone (fresh cache) the badge appears correctly.

## Decisions

1. **`Cache-Control: no-cache` on all static responses**, via a `StaticFiles`
   subclass. Browsers revalidate every load; unchanged files return a cheap
   `304` (ETag already present), changes are picked up immediately. Chosen over
   query-string versioning (manual, forgettable) and hashed filenames (needs a
   build step this no-build app doesn't have).
2. **Focused mobile pass** in CSS only — no layout redesign.

> One-time caveat: the phone already cached the old assets *without* this
> header, so it keeps its heuristic-stale copy until cleared. The user clears
> site data / loads once in a private tab to get current; `no-cache` keeps it
> fresh from then on.

## Backend (`main.py`)

Replace the plain `StaticFiles` mount with a no-cache subclass. Define it just
above the existing mount block and use it in the mount:

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

## Frontend (`static/style.css`)

**Always-on (defensive):** let the card header wrap so the platform + `×N` +
Owned badges can never overflow/clip on a narrow card. Modify `.card-top`:

```css
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 8px;
}
```

**Phone-only:** extend the existing `@media (max-width: 640px)` block with
larger touch targets, a tighter modal, and a single-column form split:

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

(The first four lines already exist in that block; the new rules are appended
inside it.)

## Scope / non-goals

- No bottom-sheet modal, no nav changes, no type-scale overhaul (that was the
  "mobile-first redesign" option, not chosen).
- `index.html` already has `<meta name="viewport" ...>` — no change needed.
- No new dependencies.

## Testing

- **Backend (`test_cache_headers.py`, new):** GET `/app.js` and `/style.css`
  from the running server and assert the response includes
  `Cache-Control: no-cache`.
- **Manual (user, on phone):** after deploy + clearing site data once, confirm
  in a *normal* tab that the `×N` badge and the scan banner appear, the card
  header never overflows, and Edit/Delete/filter/sort buttons are comfortably
  tappable.

## Files touched

- `main.py` — `NoCacheStaticFiles` subclass + use it in the mount
- `static/style.css` — `.card-top` wrap + mobile `@media` additions
- `test_cache_headers.py` (new) — asserts `Cache-Control: no-cache`
