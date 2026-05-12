import sqlite3
import os
from datetime import date

# Database file lives alongside this script
DB_PATH = os.path.join(os.path.dirname(__file__), "pantry.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    return conn


def init_db():
    """Create the items table if it doesn't already exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                date_added  DATE    NOT NULL,
                expiry_date DATE    NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def get_all_items():
    """Return all items sorted by expiry date ascending."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM items ORDER BY expiry_date ASC"
        ).fetchall()
    return [dict(row) for row in rows]


def add_item(name: str, expiry_date: str) -> int:
    """Insert a new item. expiry_date should be an ISO date string (YYYY-MM-DD).
    Returns the new row id."""
    today = date.today().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO items (name, date_added, expiry_date) VALUES (?, ?, ?)",
            (name, today, expiry_date),
        )
        conn.commit()
        return cursor.lastrowid


def delete_item(item_id: int) -> bool:
    """Delete an item by id. Returns True if a row was deleted."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        return cursor.rowcount > 0
