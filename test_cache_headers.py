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
