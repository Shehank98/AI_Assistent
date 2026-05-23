"""
memory/store.py — Persistent memory using SQLite
Stores long-term facts + conversation summaries.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / ".jarvis" / "memory.db"


class MemoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                summary    TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self.conn.commit()

    # ── Facts (long-term user info) ───────────────────────────────────────────

    def save_fact(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO facts (key, value, updated_at) VALUES (?, ?, ?)",
            (key.lower().strip(), value, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_fact(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM facts WHERE key = ?", (key.lower().strip(),)
        ).fetchone()
        return row[0] if row else None

    def get_all_facts(self) -> dict:
        rows = self.conn.execute("SELECT key, value FROM facts").fetchall()
        return {k: v for k, v in rows}

    def delete_fact(self, key: str):
        self.conn.execute("DELETE FROM facts WHERE key = ?", (key.lower().strip(),))
        self.conn.commit()

    # ── Conversation summaries ────────────────────────────────────────────────

    def save_conversation_summary(self, summary: str):
        self.conn.execute(
            "INSERT INTO conversations (summary, created_at) VALUES (?, ?)",
            (summary, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_recent_summaries(self, n: int = 5) -> list[str]:
        rows = self.conn.execute(
            "SELECT summary FROM conversations ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return [r[0] for r in rows]

    def close(self):
        self.conn.close()
