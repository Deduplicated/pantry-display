import sqlite3
import os
from datetime import date, timedelta

from defaults import USE_BY_OFFSET_DAYS

# Database file lives alongside this script
DB_PATH = os.path.join(os.path.dirname(__file__), "pantry.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    return conn


def default_use_by_date(expiry_date: str) -> str:
    """Return use_by_date as expiry minus USE_BY_OFFSET_DAYS."""
    expiry = date.fromisoformat(expiry_date)
    return (expiry - timedelta(days=USE_BY_OFFSET_DAYS)).isoformat()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add use_by_date column to existing databases."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    if "use_by_date" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN use_by_date DATE")
        conn.execute(
            """
            UPDATE items
            SET use_by_date = date(expiry_date, ?)
            WHERE use_by_date IS NULL
            """,
            (f"-{USE_BY_OFFSET_DAYS} days",),
        )


def init_db():
    """Create the items table if it doesn't already exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                date_added  DATE    NOT NULL,
                expiry_date DATE    NOT NULL,
                use_by_date DATE,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _migrate(conn)
        conn.commit()


def get_all_items():
    """Return all items sorted by expiry date ascending."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM items ORDER BY expiry_date ASC"
        ).fetchall()
    return [dict(row) for row in rows]


def add_item(name: str, expiry_date: str, use_by_date: str | None = None) -> int:
    """Insert a new item. Dates are ISO strings (YYYY-MM-DD).
    If use_by_date is omitted, it defaults to expiry_date minus USE_BY_OFFSET_DAYS.
    Returns the new row id."""
    if use_by_date is None:
        use_by_date = default_use_by_date(expiry_date)

    today = date.today().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO items (name, date_added, expiry_date, use_by_date)
            VALUES (?, ?, ?, ?)
            """,
            (name, today, expiry_date, use_by_date),
        )
        conn.commit()
        return cursor.lastrowid


def update_item(
    item_id: int,
    *,
    expiry_date: str | None = None,
    use_by_date: str | None = None,
) -> bool:
    """Update dates on an existing item. Returns True if the row exists."""
    fields = []
    values = []
    if expiry_date is not None:
        fields.append("expiry_date = ?")
        values.append(expiry_date)
    if use_by_date is not None:
        fields.append("use_by_date = ?")
        values.append(use_by_date)
    if not fields:
        return False

    values.append(item_id)
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE items SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_item(item_id: int) -> bool:
    """Delete an item by id. Returns True if a row was deleted."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        return cursor.rowcount > 0
