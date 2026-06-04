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
    scraped_at     TIMESTAMP DEFAULT (datetime('now'))
)
"""

_INSERT_SQL = """
INSERT OR IGNORE INTO leads
    (google_id, name, rating, reviews_count, phone, website, address, category, scraped_at)
VALUES
    (:google_id, :name, :rating, :reviews_count, :phone, :website, :address, :category, :scraped_at)
"""


def initialize_db() -> None:
    """Create leads table if it doesn't exist. Idempotent."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(_CREATE_TABLE_SQL)


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
