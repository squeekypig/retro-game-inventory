import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "games.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            platform TEXT NOT NULL,
            release_year INTEGER,
            estimated_value REAL,
            owned INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def row_to_dict(row):
    d = dict(row)
    d["owned"] = bool(d.get("owned", 1))
    return d
