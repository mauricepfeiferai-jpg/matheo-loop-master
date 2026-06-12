#!/usr/bin/env python3
"""Schema Version — Migrations-Tracking für SQLite-Ledger."""
import sqlite3
from pathlib import Path

DB = Path("/var/lib/loop-master/ledger.db")
CURRENT_VERSION = 1

def init_migrations():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)")
    c.execute("SELECT MAX(version) FROM schema_version")
    row = c.fetchone()
    current = row[0] if row[0] else 0
    if current < CURRENT_VERSION:
        _migrate(c, current, CURRENT_VERSION)
        c.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))", (CURRENT_VERSION,))
        conn.commit()
    conn.close()

def _migrate(c, from_v, to_v):
    if from_v < 1:
        c.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                rid TEXT PRIMARY KEY,
                loop TEXT,
                phase TEXT,
                started_at TEXT,
                finished_at TEXT,
                status TEXT,
                output_path TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_loop ON ledger(loop)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_started ON ledger(started_at)")

if __name__ == "__main__":
    init_migrations()
    print(f"Schema v{CURRENT_VERSION} OK")
