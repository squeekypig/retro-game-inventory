"""Test script: identify the test cartridge image and add it to the collection."""
import json
import os
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

# ── Step 1: Identify the game from the photo ──────────────────────────────────
img_path = os.path.join(os.path.dirname(__file__), "test_cart.jpg")

boundary = "----TestBoundary12345"
with open(img_path, "rb") as f:
    img_bytes = f.read()

body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="test_cart.jpg"\r\n'
    f"Content-Type: image/jpeg\r\n"
    f"\r\n"
).encode() + img_bytes + f"\r\n--{boundary}--\r\n".encode()

req = urllib.request.Request(
    f"{BASE}/api/identify",
    data=body,
    method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)

print("Sending image to Claude for identification...")
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        identified = json.loads(resp.read())
except urllib.error.HTTPError as e:
    print(f"Error: {e.code} — {e.read().decode()}")
    raise

print(f"\nIdentified game:")
print(f"  Title:      {identified.get('title')}")
print(f"  Platform:   {identified.get('platform')}")
print(f"  Year:       {identified.get('release_year')}")
print(f"  Confidence: {identified.get('confidence')}")
if identified.get("notes"):
    print(f"  Notes:      {identified.get('notes')}")

# ── Step 2: Save it to the database ──────────────────────────────────────────
game_data = {
    "title":          identified["title"],
    "platform":       identified["platform"],
    "release_year":   identified.get("release_year"),
    "estimated_value": 45.00,  # test value
    "owned":          True,
    "notes":          identified.get("notes") or "Test entry",
}

req2 = urllib.request.Request(
    f"{BASE}/api/games",
    data=json.dumps(game_data).encode(),
    method="POST",
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(req2) as resp:
    saved = json.loads(resp.read())

print(f"\nSaved to collection (ID: {saved['id']})")

# ── Step 3: Check stats ───────────────────────────────────────────────────────
with urllib.request.urlopen(f"{BASE}/api/stats") as resp:
    stats = json.loads(resp.read())

print(f"\nCollection stats:")
print(f"  Total games:      {stats['total']}")
print(f"  Owned:            {stats['owned']}")
print(f"  Collection value: ${stats['collection_value']:.2f}")
print(f"\nOpen http://localhost:8000 to see your collection!")
