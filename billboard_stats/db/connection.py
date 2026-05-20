"""SQLite connection management."""

import os
import sqlite3
from pathlib import Path

# Path to the SQLite database file
DB_PATH = Path(__file__).resolve().parent.parent.parent / "billboard.db"


def get_conn():
    """Get a connection to the SQLite database."""
    # Ensure the directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    # Return rows as dict-like objects
    conn.row_factory = sqlite3.Row
    return conn


def put_conn(conn):
    """Close the SQLite connection (no pooling needed for local build)."""
    if conn:
        conn.close()


def close_pool():
    """No-op for SQLite."""
    pass


def execute_query(query: str, params=None, fetch: bool = True):
    """Execute a query and optionally return results."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Convert %s (Postgres) to ? (SQLite) if necessary
        # This is a naive conversion for simple queries; complex ones might need manual fixing.
        query = query.replace("%s", "?")
        
        cur.execute(query, params or ())
        if fetch:
            rows = cur.fetchall()
            return [dict(row) for row in rows]
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)


def execute_script(sql: str):
    """Execute a multi-statement SQL script."""
    conn = get_conn()
    try:
        # SQLite's executescript doesn't support parameters and handles transactions automatically
        conn.executescript(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)
