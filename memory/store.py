"""
memory/store.py — Persistent memory using SQLite with optional Fernet encryption.
Sensitive columns (fact values, task text, preferences, mood logs) are encrypted
when the cryptography package is installed and JARVIS_SECRET_KEY or ~/.jarvis/.secret exists.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".jarvis" / "memory.db"
_SECRET_FILE = Path.home() / ".jarvis" / ".secret"


def _load_fernet():
    try:
        from cryptography.fernet import Fernet
        key_str = os.environ.get("JARVIS_SECRET_KEY", "")
        if key_str:
            key = key_str.encode()
        elif _SECRET_FILE.exists():
            key = _SECRET_FILE.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
            _SECRET_FILE.write_bytes(key)
            _SECRET_FILE.chmod(0o600)
            print(f"[memory] Generated encryption key at {_SECRET_FILE}")
        return Fernet(key)
    except ImportError:
        print("[memory] cryptography not installed — data stored unencrypted.")
        return None
    except Exception as e:
        print(f"[memory] Encryption init failed: {e} — storing unencrypted")
        return None


class MemoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._fernet = _load_fernet()
        self._init_schema()

    def _enc(self, value: str) -> str:
        if self._fernet is None:
            return value
        return self._fernet.encrypt(value.encode()).decode()

    def _dec(self, value: str) -> str:
        if self._fernet is None:
            return value
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except Exception:
            return value  # legacy unencrypted data

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

            CREATE TABLE IF NOT EXISTS preferences (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                category   TEXT NOT NULL,
                preference TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(category, preference)
            );

            CREATE TABLE IF NOT EXISTS routines (
                name        TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mood_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                mood       TEXT NOT NULL,
                context    TEXT,
                logged_at  TEXT NOT NULL
            );
        """)
        self.conn.commit()

    # ── Facts ─────────────────────────────────────────────────────────────────

    def save_fact(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO facts (key, value, updated_at) VALUES (?, ?, ?)",
            (key.lower().strip(), self._enc(value), datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_fact(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM facts WHERE key = ?", (key.lower().strip(),)
        ).fetchone()
        return self._dec(row[0]) if row else None

    def get_all_facts(self) -> dict:
        rows = self.conn.execute("SELECT key, value FROM facts").fetchall()
        return {k: self._dec(v) for k, v in rows}

    def delete_fact(self, key: str):
        self.conn.execute("DELETE FROM facts WHERE key = ?", (key.lower().strip(),))
        self.conn.commit()

    # ── Preferences ───────────────────────────────────────────────────────────

    def save_preference(self, category: str, preference: str):
        self.conn.execute(
            """INSERT INTO preferences (category, preference, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(category, preference) DO UPDATE SET updated_at=excluded.updated_at""",
            (category.lower().strip(), self._enc(preference), datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_preferences(self, category: str = "") -> list[dict]:
        if category:
            rows = self.conn.execute(
                "SELECT category, preference FROM preferences WHERE category = ?",
                (category.lower().strip(),)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT category, preference FROM preferences").fetchall()
        return [{"category": r[0], "preference": self._dec(r[1])} for r in rows]

    # ── Routines ──────────────────────────────────────────────────────────────

    def save_routine(self, name: str, description: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO routines (name, description, updated_at) VALUES (?, ?, ?)",
            (name.lower().strip(), self._enc(description), datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_routines(self) -> dict:
        rows = self.conn.execute("SELECT name, description FROM routines").fetchall()
        return {r[0]: self._dec(r[1]) for r in rows}

    # ── Mood Logs ─────────────────────────────────────────────────────────────

    def log_mood(self, mood: str, context: str = ""):
        self.conn.execute(
            "INSERT INTO mood_logs (mood, context, logged_at) VALUES (?, ?, ?)",
            (mood, self._enc(context) if context else "", datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_mood_history(self, days: int = 7) -> list[dict]:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            "SELECT mood, context, logged_at FROM mood_logs WHERE logged_at > ? ORDER BY logged_at DESC",
            (cutoff,)
        ).fetchall()
        return [{"mood": r[0], "context": self._dec(r[1]) if r[1] else "", "at": r[2]} for r in rows]

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def add_task(self, task: str, due_date: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO tasks (task, due_date, done, created_at) VALUES (?, ?, 0, ?)",
            (self._enc(task), due_date, datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_tasks(self, done: bool = False) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, task, due_date, done FROM tasks WHERE done = ?", (1 if done else 0,)
        ).fetchall()
        return [{"id": r[0], "task": self._dec(r[1]), "due_date": r[2], "done": bool(r[3])} for r in rows]

    def list_tasks_due_today(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT id, task, due_date FROM tasks WHERE done = 0 AND due_date = ?", (today,)
        ).fetchall()
        return [{"id": r[0], "task": self._dec(r[1]), "due_date": r[2]} for r in rows]

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
