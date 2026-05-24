"""
rag/store.py — pgvector document store.
Requires PostgreSQL with the pgvector extension enabled.
Uses psycopg2 directly (already in requirements.txt).
"""

import json
import os
import threading

from .embeddings import EMBEDDING_DIM

_conn = None
_lock = threading.Lock()


def _get_conn():
    global _conn
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set — pgvector requires PostgreSQL on Railway")
    with _lock:
        try:
            if _conn is not None and not _conn.closed:
                _conn.isolation_level  # quick liveness check
                return _conn
        except Exception:
            pass
        import psycopg2
        _conn = psycopg2.connect(db_url)
        _conn.autocommit = False
        return _conn


def _vec(v: list[float]) -> str:
    """Format embedding list as pgvector literal string."""
    return "[" + ",".join(f"{x:.8f}" for x in v) + "]"


def setup():
    """
    Create pgvector extension + jarvis_docs table.
    Safe to call multiple times (uses IF NOT EXISTS).
    Run `CREATE EXTENSION IF NOT EXISTS vector;` manually in Railway DB
    console first if this fails with 'extension not found'.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS jarvis_docs (
                id         SERIAL PRIMARY KEY,
                content    TEXT        NOT NULL,
                source     TEXT        NOT NULL DEFAULT '',
                metadata   JSONB       NOT NULL DEFAULT '{{}}',
                embedding  vector({EMBEDDING_DIM}),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        # Index only if enough rows exist (ivfflat needs ≥ lists rows)
        cur.execute("SELECT COUNT(*) FROM jarvis_docs")
        row_count = cur.fetchone()[0]
        if row_count >= 100:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS jarvis_docs_emb_idx
                ON jarvis_docs USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 50)
            """)
    conn.commit()
    print(f"[rag] pgvector store ready ({row_count} chunks)")


def add_chunks(chunks: list[dict]) -> int:
    """
    Embed and store chunks. Each chunk: {'content': str, 'source': str, 'metadata': dict}.
    Returns number of chunks stored.
    """
    from .embeddings import embed_text
    conn = _get_conn()
    stored = 0
    with conn.cursor() as cur:
        for chunk in chunks:
            text = (chunk.get("content") or "").strip()
            if not text:
                continue
            emb = embed_text(text)
            cur.execute(
                """INSERT INTO jarvis_docs (content, source, metadata, embedding)
                   VALUES (%s, %s, %s, %s::vector)""",
                (
                    text,
                    chunk.get("source", ""),
                    json.dumps(chunk.get("metadata", {})),
                    _vec(emb),
                ),
            )
            stored += 1
    conn.commit()
    return stored


def search(query: str, k: int = 5, source_filter: str = "") -> list[dict]:
    """Semantic similarity search. Returns top-k chunks."""
    from .embeddings import embed_text
    emb = embed_text(query)
    emb_str = _vec(emb)
    conn = _get_conn()
    with conn.cursor() as cur:
        if source_filter:
            cur.execute(
                """SELECT content, source, metadata,
                          1 - (embedding <=> %s::vector) AS score
                   FROM jarvis_docs
                   WHERE source ILIKE %s
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s""",
                (emb_str, f"%{source_filter}%", emb_str, k),
            )
        else:
            cur.execute(
                """SELECT content, source, metadata,
                          1 - (embedding <=> %s::vector) AS score
                   FROM jarvis_docs
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s""",
                (emb_str, emb_str, k),
            )
        rows = cur.fetchall()
    return [
        {
            "content": r[0],
            "source": r[1],
            "metadata": r[2] or {},
            "score": round(float(r[3]), 3),
        }
        for r in rows
    ]


def list_sources() -> list[dict]:
    """Return all unique document sources with chunk counts."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT source, COUNT(*) AS chunks, MIN(created_at) AS ingested_at
            FROM jarvis_docs
            GROUP BY source
            ORDER BY ingested_at DESC
        """)
        rows = cur.fetchall()
    return [{"source": r[0], "chunks": r[1], "ingested_at": str(r[2])[:19]} for r in rows]


def delete_source(source: str) -> int:
    """Delete all chunks for a given source filename. Returns deleted count."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM jarvis_docs WHERE source = %s", (source,))
        count = cur.rowcount
    conn.commit()
    return count


def is_available() -> bool:
    """Check if pgvector store is reachable."""
    try:
        _get_conn()
        return True
    except Exception:
        return False
