"""
memory/store.py — Persistent memory.
Backend: PostgreSQL when DATABASE_URL is set, SQLite otherwise.
Sensitive columns are encrypted at rest when JARVIS_SECRET_KEY is set.
"""

import json
import os
import threading
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


class _DB:
    """
    Normalises sqlite3 and psycopg2 to one interface.
    All SQL is written with '?' placeholders; they're auto-converted to '%s'
    for PostgreSQL. Schema DDL is provided separately for each backend.
    """

    def __init__(self):
        self._lock = threading.RLock()
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            import psycopg2
            self._pg = True
            self._conn = psycopg2.connect(db_url)
            self._conn.autocommit = False
            print("[memory] PostgreSQL backend")
        else:
            import sqlite3 as _sqlite3
            self._pg = False
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._conn = _sqlite3.connect(str(DB_PATH), check_same_thread=False)
            print(f"[memory] SQLite backend → {DB_PATH}")

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self._pg else sql

    def execute(self, sql: str, params=()):
        with self._lock:
            if self._pg:
                cur = self._conn.cursor()
                cur.execute(self._sql(sql), params)
                self._conn.commit()
                return cur
            else:
                cur = self._conn.execute(self._sql(sql), params)
                self._conn.commit()
                return cur

    def fetchone(self, sql: str, params=()):
        with self._lock:
            if self._pg:
                cur = self._conn.cursor()
                cur.execute(self._sql(sql), params)
                return cur.fetchone()
            else:
                return self._conn.execute(self._sql(sql), params).fetchone()

    def fetchall(self, sql: str, params=()):
        with self._lock:
            if self._pg:
                cur = self._conn.cursor()
                cur.execute(self._sql(sql), params)
                return cur.fetchall()
            else:
                return self._conn.execute(self._sql(sql), params).fetchall()

    def insert(self, sql: str, params=()) -> int:
        """Execute INSERT and return the new row id."""
        with self._lock:
            if self._pg:
                cur = self._conn.cursor()
                cur.execute(self._sql(sql) + " RETURNING id", params)
                row = cur.fetchone()
                self._conn.commit()
                return row[0] if row else -1
            else:
                cur = self._conn.execute(self._sql(sql), params)
                self._conn.commit()
                return cur.lastrowid

    def upsert_single_key(self, table: str, key_col: str, key_val, data: dict):
        """Upsert a row with a single primary-key column."""
        cols = list(data.keys())
        vals = list(data.values())
        if self._pg:
            phs = ", ".join(["%s"] * (len(cols) + 1))
            update = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols)
            sql = (f"INSERT INTO {table} ({key_col}, {', '.join(cols)}) VALUES ({phs}) "
                   f"ON CONFLICT ({key_col}) DO UPDATE SET {update}")
            with self._lock:
                cur = self._conn.cursor()
                cur.execute(sql, (key_val, *vals))
                self._conn.commit()
        else:
            phs = ", ".join(["?"] * (len(cols) + 1))
            sql = f"INSERT OR REPLACE INTO {table} ({key_col}, {', '.join(cols)}) VALUES ({phs})"
            with self._lock:
                self._conn.execute(sql, (key_val, *vals))
                self._conn.commit()

    def upsert_composite_key(self, table: str, key_cols: list[str], key_vals: list, data: dict):
        """Upsert using a composite unique key."""
        cols = list(data.keys())
        vals = list(data.values())
        all_cols = key_cols + cols
        all_vals = key_vals + vals
        if self._pg:
            phs = ", ".join(["%s"] * len(all_cols))
            conflict = ", ".join(key_cols)
            update = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols) if cols else "TRUE=TRUE"
            sql = (f"INSERT INTO {table} ({', '.join(all_cols)}) VALUES ({phs}) "
                   f"ON CONFLICT ({conflict}) DO UPDATE SET {update}")
            with self._lock:
                cur = self._conn.cursor()
                cur.execute(sql, all_vals)
                self._conn.commit()
        else:
            phs = ", ".join(["?"] * len(all_cols))
            sql = f"INSERT OR IGNORE INTO {table} ({', '.join(all_cols)}) VALUES ({phs})"
            with self._lock:
                self._conn.execute(sql, all_vals)
                self._conn.commit()

    def create_tables(self, sqlite_stmts: list[str], pg_stmts: list[str]):
        stmts = pg_stmts if self._pg else sqlite_stmts
        with self._lock:
            if self._pg:
                cur = self._conn.cursor()
                for stmt in stmts:
                    cur.execute(stmt)
                self._conn.commit()
            else:
                for stmt in stmts:
                    self._conn.execute(stmt)
                self._conn.commit()


# Shared DDL — auto-adjusted for each backend
_SQLITE_DDL = [
    """CREATE TABLE IF NOT EXISTS facts (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS conversations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        summary    TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS tasks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        task       TEXT NOT NULL,
        due_date   TEXT,
        done       INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS preferences (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        category   TEXT NOT NULL,
        preference TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(category, preference)
    )""",
    """CREATE TABLE IF NOT EXISTS routines (
        name        TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS mood_logs (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        mood      TEXT NOT NULL,
        context   TEXT,
        logged_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS goals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'active',
        result      TEXT,
        deadline    TEXT,
        created_at  TEXT NOT NULL
    )""",
]

_PG_DDL = [s.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
           for s in _SQLITE_DDL]


class MemoryStore:
    def __init__(self):
        self._db = _DB()
        self._fernet = _load_fernet()
        self._db.create_tables(_SQLITE_DDL, _PG_DDL)

    # ── Encryption helpers ─────────────────────────────────────────────────────

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
            return value  # legacy unencrypted row

    # ── Facts ─────────────────────────────────────────────────────────────────

    def save_fact(self, key: str, value: str):
        self._db.upsert_single_key(
            "facts", "key", key.lower().strip(),
            {"value": self._enc(value), "updated_at": datetime.now().isoformat()},
        )

    def get_fact(self, key: str) -> str | None:
        row = self._db.fetchone("SELECT value FROM facts WHERE key = ?", (key.lower().strip(),))
        return self._dec(row[0]) if row else None

    def get_all_facts(self) -> dict:
        rows = self._db.fetchall("SELECT key, value FROM facts")
        return {k: self._dec(v) for k, v in rows}

    def delete_fact(self, key: str):
        self._db.execute("DELETE FROM facts WHERE key = ?", (key.lower().strip(),))

    # ── Preferences ───────────────────────────────────────────────────────────

    def save_preference(self, category: str, preference: str):
        self._db.upsert_composite_key(
            "preferences",
            key_cols=["category", "preference"],
            key_vals=[category.lower().strip(), self._enc(preference)],
            data={"updated_at": datetime.now().isoformat()},
        )

    def get_preferences(self, category: str = "") -> list[dict]:
        if category:
            rows = self._db.fetchall(
                "SELECT category, preference FROM preferences WHERE category = ?",
                (category.lower().strip(),),
            )
        else:
            rows = self._db.fetchall("SELECT category, preference FROM preferences")
        return [{"category": r[0], "preference": self._dec(r[1])} for r in rows]

    # ── Routines ──────────────────────────────────────────────────────────────

    def save_routine(self, name: str, description: str):
        self._db.upsert_single_key(
            "routines", "name", name.lower().strip(),
            {"description": self._enc(description), "updated_at": datetime.now().isoformat()},
        )

    def get_routines(self) -> dict:
        rows = self._db.fetchall("SELECT name, description FROM routines")
        return {r[0]: self._dec(r[1]) for r in rows}

    # ── Mood Logs ─────────────────────────────────────────────────────────────

    def log_mood(self, mood: str, context: str = ""):
        self._db.execute(
            "INSERT INTO mood_logs (mood, context, logged_at) VALUES (?, ?, ?)",
            (mood, self._enc(context) if context else "", datetime.now().isoformat()),
        )

    def get_mood_history(self, days: int = 7) -> list[dict]:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self._db.fetchall(
            "SELECT mood, context, logged_at FROM mood_logs WHERE logged_at > ? ORDER BY logged_at DESC",
            (cutoff,),
        )
        return [{"mood": r[0], "context": self._dec(r[1]) if r[1] else "", "at": r[2]} for r in rows]

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def add_task(self, task: str, due_date: str | None = None) -> int:
        return self._db.insert(
            "INSERT INTO tasks (task, due_date, done, created_at) VALUES (?, ?, 0, ?)",
            (self._enc(task), due_date, datetime.now().isoformat()),
        )

    def list_tasks(self, done: bool = False) -> list[dict]:
        rows = self._db.fetchall(
            "SELECT id, task, due_date, done FROM tasks WHERE done = ?", (1 if done else 0,)
        )
        return [{"id": r[0], "task": self._dec(r[1]), "due_date": r[2], "done": bool(r[3])} for r in rows]

    def list_tasks_due_today(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self._db.fetchall(
            "SELECT id, task, due_date FROM tasks WHERE done = 0 AND due_date = ?", (today,)
        )
        return [{"id": r[0], "task": self._dec(r[1]), "due_date": r[2]} for r in rows]

    def complete_task(self, task_id: int):
        self._db.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))

    # ── Goals ─────────────────────────────────────────────────────────────────

    def create_goal(self, description: str, deadline: str | None = None) -> int:
        return self._db.insert(
            "INSERT INTO goals (description, status, deadline, created_at) VALUES (?, 'active', ?, ?)",
            (description, deadline, datetime.now().isoformat()),
        )

    def list_goals(self, status: str | None = "active") -> list[dict]:
        if status:
            rows = self._db.fetchall(
                "SELECT id, description, status, deadline, result FROM goals WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            rows = self._db.fetchall(
                "SELECT id, description, status, deadline, result FROM goals ORDER BY created_at DESC"
            )
        return [
            {"id": r[0], "description": r[1], "status": r[2], "deadline": r[3], "result": r[4]}
            for r in rows
        ]

    def update_goal(self, goal_id: int, status: str, result: str | None = None):
        if result is not None:
            self._db.execute(
                "UPDATE goals SET status=?, result=? WHERE id=?", (status, result, goal_id)
            )
        else:
            self._db.execute("UPDATE goals SET status=? WHERE id=?", (status, goal_id))

    # ── Conversations ─────────────────────────────────────────────────────────

    def save_conversation_summary(self, summary: str):
        self._db.execute(
            "INSERT INTO conversations (summary, created_at) VALUES (?, ?)",
            (summary, datetime.now().isoformat()),
        )

    def get_recent_summaries(self, n: int = 5) -> list[str]:
        rows = self._db.fetchall(
            "SELECT summary FROM conversations ORDER BY id DESC LIMIT ?", (n,)
        )
        return [r[0] for r in rows]

    def close(self):
        try:
            self._db._conn.close()
        except Exception:
            pass
