"""
Local SQLite database for tracking DM outreach.
Stores company -> employees mapping and who has been messaged.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "dm_outreach.db")


def _get_connection():
    """Get a connection to the SQLite database, creating tables if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messaged_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_url TEXT NOT NULL,
            company_name TEXT,
            person_name TEXT NOT NULL,
            person_title TEXT,
            profile_url TEXT,
            message_sent TEXT,
            messaged_at TEXT NOT NULL,
            UNIQUE(company_url, person_name)
        )
    """)
    conn.commit()
    return conn


def is_already_messaged(company_url: str, person_name: str) -> bool:
    """Check if we have already messaged this person for this company."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM messaged_people WHERE company_url = ? AND person_name = ?",
            (company_url, person_name)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_all_messaged_names(company_url: str) -> set:
    """Get all people we have messaged for a given company URL."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT person_name FROM messaged_people WHERE company_url = ?",
            (company_url,)
        ).fetchall()
        return {row["person_name"] for row in rows}
    finally:
        conn.close()


def get_all_messaged_names_global() -> set:
    """Get ALL people we have ever messaged across all companies."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT person_name FROM messaged_people").fetchall()
        return {row["person_name"] for row in rows}
    finally:
        conn.close()


def record_message(company_url: str, company_name: str, person_name: str,
                   person_title: str, profile_url: str, message_sent: str):
    """Record that we messaged a person. Ignores duplicates."""
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO messaged_people
               (company_url, company_name, person_name, person_title, profile_url, message_sent, messaged_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (company_url, company_name, person_name, person_title,
             profile_url, message_sent, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_campaign_history() -> list:
    """Get all outreach history for display in the UI."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM messaged_people ORDER BY messaged_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_company_stats() -> list:
    """Get message counts per company."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT company_name, company_url, COUNT(*) as total_messaged,
                      MAX(messaged_at) as last_messaged
               FROM messaged_people
               GROUP BY company_url
               ORDER BY last_messaged DESC"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
