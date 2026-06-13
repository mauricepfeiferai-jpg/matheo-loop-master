#!/usr/bin/env python3
"""Discussion Memory — pro Proposal Gespraechskontext speichern.

Ermoeglicht langandauernde Diskussionen mit Maurice ueber Telegram,
ohne dass der Kontext verloren geht zwischen einzelnen Nachrichten.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/var/lib/loop-master/discussions.db")


@dataclass
class Message:
    role: str   # "user" oder "hecate"
    content: str
    ts: str = ""

    def __post_init__(self):
        if not self.ts:
            self.ts = datetime.now(timezone.utc).isoformat()


class DiscussionMemory:
    """SQLite-basierte Diskussionshistorie fuer Proposals."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discussions (
                    proposal_id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    messages TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_discussions_updated
                ON discussions(updated_at)
                """
            )

    def get_or_create(self, proposal_id: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT status, messages FROM discussions WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            now = datetime.now(timezone.utc).isoformat()
            if row is None:
                conn.execute(
                    "INSERT INTO discussions (proposal_id, status, created_at, updated_at, messages) VALUES (?, ?, ?, ?, ?)",
                    (proposal_id, "open", now, now, "[]"),
                )
                return {"proposal_id": proposal_id, "status": "open", "messages": []}
            return {
                "proposal_id": proposal_id,
                "status": row[0],
                "messages": [Message(**m) for m in json.loads(row[1])],
            }

    def add_message(self, proposal_id: str, role: str, content: str) -> None:
        disc = self.get_or_create(proposal_id)
        messages = disc["messages"]
        messages.append(Message(role=role, content=content))
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE discussions SET messages = ?, updated_at = ? WHERE proposal_id = ?",
                (json.dumps([{"role": m.role, "content": m.content, "ts": m.ts} for m in messages]), now, proposal_id),
            )

    def set_status(self, proposal_id: str, status: str) -> None:
        assert status in {"open", "approved", "rejected", "plan_only", "details"}
        self.get_or_create(proposal_id)  # sicherstellen, dass Zeile existiert
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO discussions (proposal_id, status, created_at, updated_at, messages) "
                "VALUES (?, ?, ?, ?, '[]') "
                "ON CONFLICT(proposal_id) DO UPDATE SET status = ?, updated_at = ?",
                (proposal_id, status, now, now, status, now),
            )

    def get_context(self, proposal_id: str, max_messages: int = 20) -> str:
        disc = self.get_or_create(proposal_id)
        msgs = disc["messages"][-max_messages:]
        lines = []
        for m in msgs:
            who = "Maurice" if m.role == "user" else "HECATE"
            lines.append(f"{who}: {m.content}")
        return "\n".join(lines)

    def list_open(self, limit: int = 10) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT proposal_id, status, updated_at FROM discussions WHERE status = 'open' ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [{"proposal_id": r[0], "status": r[1], "updated_at": r[2]} for r in rows]
