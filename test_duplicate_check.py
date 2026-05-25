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
