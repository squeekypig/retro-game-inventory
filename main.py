import base64
import json
import os
from pathlib import Path
from typing import Optional

import anthropic
from anthropic import Anthropic
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import get_db, init_db, row_to_dict

app = FastAPI(title="Retro Game Inventory")

PLACEHOLDER_API_KEY = "your-api-key-here"
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

if not API_KEY:
    print(
        "WARNING: ANTHROPIC_API_KEY is not set. Photo identification and value "
        "lookup will fail until you set a valid key and restart the server."
    )
elif API_KEY == PLACEHOLDER_API_KEY:
    print(
        f"WARNING: ANTHROPIC_API_KEY is still the placeholder '{PLACEHOLDER_API_KEY}'. "
        "Replace it in start.bat (or your environment) with a real key, then restart "
        "the server."
    )

# Pass the key explicitly with a non-empty fallback so a missing key doesn't crash
# startup; an invalid key then surfaces as a clear error on the first API call.
client = Anthropic(api_key=API_KEY or PLACEHOLDER_API_KEY)

init_db()


def call_claude(**kwargs):
    """Call the Claude API, translating SDK errors into clear HTTP responses.

    Auth/permission failures mean the server's own ANTHROPIC_API_KEY is bad, so we
    report them as 500 (server misconfiguration) with an actionable message rather
    than a misleading 502 Bad Gateway.
    """
    try:
        return client.messages.create(**kwargs)
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=500,
            detail="Anthropic API key is invalid or missing. Set a valid "
                   "ANTHROPIC_API_KEY and restart the server.",
        )
    except anthropic.PermissionDeniedError:
        raise HTTPException(
            status_code=500,
            detail="Anthropic API key lacks permission for this request. "
                   "Check the key's settings in the Anthropic Console.",
        )
    except anthropic.RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Claude API rate limit reached. Wait a moment and try again.",
        )
    except anthropic.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach the Claude API: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected Claude API error: {type(e).__name__}: {e}")

VALID_SORTS = {"title", "platform", "release_year", "estimated_value", "created_at"}
VALID_ORDERS = {"asc", "desc"}


class GameCreate(BaseModel):
    title: str
    platform: str
    release_year: Optional[int] = None
    estimated_value: Optional[float] = None
    owned: bool = True
    notes: Optional[str] = None


class GameUpdate(BaseModel):
    title: Optional[str] = None
    platform: Optional[str] = None
    release_year: Optional[int] = None
    estimated_value: Optional[float] = None
    owned: Optional[bool] = None
    notes: Optional[str] = None


class ValueLookup(BaseModel):
    title: str
    platform: str


@app.post("/api/identify")
async def identify_game(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    media_type = file.content_type or "image/jpeg"
    if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        media_type = "image/jpeg"

    image_b64 = base64.standard_b64encode(content).decode("utf-8")

    response = call_claude(
        model="claude-opus-4-7",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    }
                },
                {
                    "type": "text",
                    "text": (
                        "Identify this retro video game from the photo. "
                        "It may be a cartridge, box/case, or disc.\n\n"
                        "Return ONLY a JSON object with these fields:\n"
                        "{\n"
                        '  "title": "exact game title",\n'
                        '  "platform": "platform name (e.g. NES, SNES, N64, Game Boy, GBC, GBA, '
                        "GameCube, Wii, PS1, PS2, PS3, Sega Genesis, Sega Saturn, Dreamcast, "
                        'Atari 2600, Atari 7800, etc.)",\n'
                        '  "release_year": year as integer or null,\n'
                        '  "confidence": "high" | "medium" | "low",\n'
                        '  "notes": "brief notes or null"\n'
                        "}\n\n"
                        "Return ONLY the JSON, no markdown, no extra text."
                    )
                }
            ]
        }]
    )

    text = next((b.text for b in response.content if b.type == "text"), "{}")
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Could not parse game identification response")


@app.get("/api/games")
def list_games(
    sort: str = "title",
    order: str = "asc",
    platform: Optional[str] = None,
    owned: Optional[str] = None,
    search: Optional[str] = None,
):
    sort = sort if sort in VALID_SORTS else "title"
    order = order if order in VALID_ORDERS else "asc"

    query = "SELECT * FROM games WHERE 1=1"
    params: list = []

    if platform:
        query += " AND platform = ?"
        params.append(platform)
    if owned == "true":
        query += " AND owned = 1"
    elif owned == "false":
        query += " AND owned = 0"
    if search:
        query += " AND title LIKE ?"
        params.append(f"%{search}%")

    query += f" ORDER BY {sort} COLLATE NOCASE {order.upper()}"

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


@app.get("/api/games/{game_id}")
def get_game(game_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Game not found")
    return row_to_dict(row)


@app.post("/api/games", status_code=201)
def create_game(game: GameCreate):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO games (title, platform, release_year, estimated_value, owned, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (game.title, game.platform, game.release_year, game.estimated_value,
         1 if game.owned else 0, game.notes),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM games WHERE id = ?", (cursor.lastrowid,)).fetchone()
    conn.close()
    return row_to_dict(row)


@app.put("/api/games/{game_id}")
def update_game(game_id: int, game: GameUpdate):
    conn = get_db()
    if not conn.execute("SELECT id FROM games WHERE id = ?", (game_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Game not found")

    updates = {k: v for k, v in game.model_dump().items() if v is not None}
    if "owned" in updates:
        updates["owned"] = 1 if updates["owned"] else 0

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE games SET {set_clause} WHERE id = ?",
            [*updates.values(), game_id],
        )
        conn.commit()

    row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    conn.close()
    return row_to_dict(row)


@app.delete("/api/games/{game_id}")
def delete_game(game_id: int):
    conn = get_db()
    if not conn.execute("SELECT id FROM games WHERE id = ?", (game_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Game not found")
    conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/platforms")
def list_platforms():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT platform FROM games ORDER BY platform COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return [r["platform"] for r in rows]


@app.get("/api/stats")
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM games").fetchone()["c"]
    owned = conn.execute("SELECT COUNT(*) as c FROM games WHERE owned = 1").fetchone()["c"]
    wishlist = conn.execute("SELECT COUNT(*) as c FROM games WHERE owned = 0").fetchone()["c"]
    value = conn.execute(
        "SELECT SUM(estimated_value) as v FROM games WHERE owned = 1 AND estimated_value IS NOT NULL"
    ).fetchone()["v"] or 0.0
    conn.close()
    return {"total": total, "owned": owned, "wishlist": wishlist, "collection_value": round(value, 2)}


@app.post("/api/lookup-value")
async def lookup_value(req: ValueLookup):
    prompt = (
        f"What is the current estimated retail market value of '{req.title}' for {req.platform}?\n\n"
        "Base this on recent sold listings on eBay and PriceCharting data.\n"
        "Return ONLY a JSON object:\n"
        "{\n"
        '  "loose": <loose cartridge/disc only price in USD as a number, or null>,\n'
        '  "cib": <complete in box price in USD as a number, or null>,\n'
        '  "notes": "<one sentence about rarity, demand, or notable variants, or null>"\n'
        "}\n\n"
        "Return ONLY the JSON, no markdown, no extra text."
    )
    response = call_claude(
        model="claude-opus-4-7",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = next((b.text for b in response.content if b.type == "text"), "{}")
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Could not parse value response")


# Serve static files last so API routes take precedence
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True))
