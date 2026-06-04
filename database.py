"""Storage layer: SQLite persistence via sqlite3 + pandas."""

import sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = "data.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    id             INTEGER PRIMARY KEY,
    google_id      TEXT UNIQUE NOT NULL,
    name           TEXT,
    rating         REAL,
    reviews_count  INTEGER,
    phone          TEXT,
    website        TEXT,
    address        TEXT,
    category       TEXT,
    search_query   TEXT,
    scraped_at     TIMESTAMP DEFAULT (datetime('now'))
)
"""

_INSERT_SQL = """
INSERT OR IGNORE INTO leads
    (google_id, name, rating, reviews_count, phone, website, address, category, search_query, scraped_at)
VALUES
    (:google_id, :name, :rating, :reviews_count, :phone, :website, :address, :category, :search_query, :scraped_at)
"""


def initialize_db() -> None:
    """Create leads table if it doesn't exist, migrating older schemas. Idempotent."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(_CREATE_TABLE_SQL)
        # Migrate tables created before the search_query column existed.
        existing = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
        if "search_query" not in existing:
            conn.execute("ALTER TABLE leads ADD COLUMN search_query TEXT")


def save_lead(lead_dict: dict) -> None:
    """Insert a lead with deduplication on google_id. Silently skips duplicates."""
    row = {
        "google_id":     lead_dict.get("google_id"),
        "name":          lead_dict.get("name"),
        "rating":        lead_dict.get("rating"),
        "reviews_count": lead_dict.get("reviews_count"),
        "phone":         lead_dict.get("phone"),
        "website":       lead_dict.get("website"),
        "address":       lead_dict.get("address"),
        "category":      lead_dict.get("category"),
        "search_query":  lead_dict.get("search_query", ""),
        "scraped_at":    lead_dict.get("scraped_at", datetime.utcnow().isoformat()),
    }
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(_INSERT_SQL, row)


def fetch_all_leads_as_dataframe() -> pd.DataFrame:
    """Return all leads as a pandas DataFrame."""
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM leads", conn)


def count_leads() -> int:
    """Return total number of leads stored in the database."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT COUNT(*) FROM leads").fetchone()
        return row[0] if row else 0


_EDITABLE_COLS = {
    "name", "rating", "reviews_count", "phone",
    "website", "address", "category", "search_query",
}


def update_lead(google_id: str, fields: dict) -> None:
    """Update editable columns of one lead, addressed by google_id.

    Unknown / non-editable keys are ignored. No-op if nothing editable given.
    """
    sets = {k: v for k, v in fields.items() if k in _EDITABLE_COLS}
    if not sets:
        return
    assignments = ", ".join(f"{col} = :{col}" for col in sets)
    params = dict(sets)
    params["_gid"] = google_id
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(f"UPDATE leads SET {assignments} WHERE google_id = :_gid", params)


def delete_lead(google_id: str) -> None:
    """Delete a single lead by google_id."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM leads WHERE google_id = :g", {"g": google_id})


def delete_by_query(query: str) -> int:
    """Delete all leads belonging to one query tab; return rows removed.

    The label 'Unlabeled' matches legacy rows with NULL/empty search_query.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "DELETE FROM leads "
            "WHERE COALESCE(NULLIF(search_query, ''), 'Unlabeled') = :q",
            {"q": query},
        )
        return cur.rowcount


def delete_all() -> None:
    """Remove every lead from the table."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM leads")


if __name__ == "__main__":
    initialize_db()
    sample = {
        "google_id": "ChIJtest123",
        "name": "Test Café",
        "rating": 4.5,
        "reviews_count": 120,
        "phone": "+1-800-555-0100",
        "website": "https://example.com",
        "address": "123 Main St",
        "category": "Café",
    }
    save_lead(sample)
    save_lead(sample)
    print(fetch_all_leads_as_dataframe())
