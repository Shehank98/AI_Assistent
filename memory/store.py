"""
memory/store.py — Persistent memory using SQLite
Stores long-term facts, tasks, and conversation summaries.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".jarvis" / "memory.db"


class MemoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                summary    TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                task       TEXT NOT NULL,
                due_date   TEXT,
                done       INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
        """)
        self.conn.commit()

    # ── Facts ─────────────────────────────────────────────────────────────────

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

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def add_task(self, task: str, due_date: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO tasks (task, due_date, done, created_at) VALUES (?, ?, 0, ?)",
            (task, due_date, datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_tasks(self, done: bool = False) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, task, due_date, done FROM tasks WHERE done = ?", (1 if done else 0,)
        ).fetchall()
        return [{"id": r[0], "task": r[1], "due_date": r[2], "done": bool(r[3])} for r in rows]

    def list_tasks_due_today(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT id, task, due_date FROM tasks WHERE done = 0 AND due_date = ?", (today,)
        ).fetchall()
        return [{"id": r[0], "task": r[1], "due_date": r[2]} for r in rows]

    def complete_task(self, task_id: int):
        self.conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        self.conn.commit()

    # ── Conversations ─────────────────────────────────────────────────────────

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
