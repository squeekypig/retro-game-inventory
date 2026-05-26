# Duplicate-copy detection & multi-copy indicator

- **Date:** 2026-05-25
- **Status:** Approved (design)
- **Component:** RetroVault — photo-scan add flow + collection grid

## Goal

When a user scans a game they already have, tell them it's already in the
collection — without blocking them from intentionally adding a second copy.
Show, at a glance, which games in the collection have multiple copies.

## Decisions

1. **Copies are separate rows.** Adding a second copy inserts another row in
   `games` via the existing `POST /api/games`. Each copy keeps its own value,
   notes, and condition. No schema change.
2. **A "duplicate" = same title + platform, case-insensitive, any status.** A
   match is flagged whether the existing copy is Owned or on the Wishlist.
3. **Grid shows separate cards** for each copy, each tagged with a `×N` badge.
   Copies are not collapsed into one card (keeps per-copy edit/delete simple).

## Backend (`main.py`)

New endpoint:

```
GET /api/duplicate-check?title=<str>&platform=<str>
```

- Case-insensitive exact match on both `title` and `platform`
  (`WHERE title = ? COLLATE NOCASE AND platform = ? COLLATE NOCASE`).
- Response:
  ```json
  { "count": 2, "owned": 1, "wishlist": 1 }
  ```
- Path is `/api/duplicate-check`, NOT `/api/games/duplicate-check`, to avoid
  colliding with the existing typed route `/api/games/{game_id}` (int).
- No other backend changes; adding a copy reuses `POST /api/games`.

## Frontend

### Scan-time notification (`index.html`, `app.js`, `style.css`)
- Add a hidden banner element in the modal, above the shared form
  (e.g. `<div id="dup-warning" class="dup-warning hidden"></div>`).
- After `identifyGame()` populates title + platform, call
  `/api/duplicate-check`. If `count > 0`, populate and show the banner:
  - Owned copies present: "Already in your collection — {title} ({platform}),
    you own N cop(y/ies). Saving will add another copy."
  - Wishlist-only: phrase as "on your wishlist" instead.
- When the banner is visible, relabel the Save button to "➕ Add Another Copy".
- Reset the banner + Save label whenever the modal opens (`openModal`) or the
  photo is cleared (`clearPhoto`).
- Saving is never blocked; the banner is purely informational.

### Multi-copy indicator on the grid (`app.js`, `style.css`)
- In `renderGames()`, group the loaded games by
  `title.toLowerCase() + '|' + platform.toLowerCase()`.
- Every card in a group of size ≥ 2 gets a badge in the card header,
  e.g. `📦 ×2`, alongside the existing platform/owned badges.
- Count is computed from the currently-loaded list (reflects the active
  filter; acceptable).

## Scope / non-goals

- Triggers on the **photo-scan** flow only. Manual entry does not show the
  banner (easy to add later; omitted per YAGNI).
- No merge/rollup of copies into a single card.
- No per-copy "condition" field (copies already support independent notes).

## Testing

- **Backend script** (urllib, like `test_add_game.py`): insert a game, then
  assert `/api/duplicate-check` returns `count`/`owned`/`wishlist` correctly;
  verify case-insensitive title/platform match and that a different platform
  returns `count: 0`.
- **Manual run-through:** scan a game already in the collection → banner shows
  and Save relabels; save it → grid shows `×2` badge on both cards.

## Files touched

- `main.py` — new `/api/duplicate-check` endpoint
- `static/index.html` — banner element
- `static/app.js` — duplicate check call, banner render/reset, Save relabel,
  grid grouping + badge
- `static/style.css` — `.dup-warning` and `.copies-badge` styles
- `test_duplicate_check.py` (new) — endpoint test
