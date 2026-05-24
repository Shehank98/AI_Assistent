"""
tools/rag_tool.py — RAG document tools for Jarvis.
All functions catch their own errors and return recovery-oriented strings
so Gemini can diagnose and route around failures autonomously.
"""

import os


def _pg_available() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def _recover(tool: str, exc: Exception) -> str:
    """Convert an exception into an actionable string Jarvis can reason about."""
    msg = str(exc)
    if "GEMINI_API_KEY" in msg:
        return f"[{tool}] FAILED: GEMINI_API_KEY missing or invalid. Cannot embed text."
    if "HTTP 400" in msg or "HTTP 403" in msg:
        return f"[{tool}] FAILED: Gemini API rejected the request — {msg[:200]}"
    if "Network error" in msg or "URLError" in msg:
        return f"[{tool}] FAILED: Cannot reach Gemini API. Check network connectivity."
    if "DATABASE_URL" in msg or "psycopg2" in msg or "connection" in msg.lower():
        return (
            f"[{tool}] FAILED: PostgreSQL connection error — {msg[:200]}. "
            "Inform user the document store is temporarily unavailable."
        )
    if "vector" in msg.lower() and "not exist" in msg.lower():
        return (
            f"[{tool}] FAILED: pgvector extension not enabled. "
            "Tell user to run `CREATE EXTENSION IF NOT EXISTS vector;` "
            "in the Railway PostgreSQL console."
        )
    return f"[{tool}] FAILED: {msg[:300]}"


def query_docs(query: str, k: int = 5, source: str = "") -> str:
    """Semantic search across all uploaded documents and spreadsheets."""
    if not _pg_available():
        return "[query_docs] Unavailable — no PostgreSQL configured (DATABASE_URL missing)."
    try:
        from rag.store import search
        results = search(query, k=k, source_filter=source)
        if not results:
            return (
                f"No relevant content found for '{query}' in the knowledge base. "
                "If a file was recently uploaded, it may still be indexing. "
                "Use list_documents to check what's available."
            )
        lines = [f"Found {len(results)} passage(s) matching '{query}':\n"]
        for i, r in enumerate(results, 1):
            meta = r.get("metadata") or {}
            pct = int(r["score"] * 100)
            loc = r.get("source", "unknown")
            if meta.get("sheet"):
                loc += f" / sheet '{meta['sheet']}' rows {meta.get('row_start','?')}–{meta.get('row_end','?')}"
            elif meta.get("page"):
                loc += f" / page {meta['page']}"
            elif meta.get("slide"):
                loc += f" / slide {meta['slide']}"
            lines.append(f"[{i}] {pct}% — {loc}\n{r['content'][:500]}\n")
        return "\n".join(lines)
    except Exception as exc:
        return _recover("query_docs", exc)


def list_documents() -> str:
    """List all files indexed in the knowledge base."""
    if not _pg_available():
        return "[list_documents] Unavailable — DATABASE_URL not set."
    try:
        from rag.store import list_sources
        sources = list_sources()
        if not sources:
            return (
                "No documents indexed yet. "
                "User can upload files via the 📎 button in the chat interface, "
                "or via POST /api/upload."
            )
        lines = ["Indexed documents:"]
        for s in sources:
            lines.append(
                f"  • {s['source']} — {s['chunks']} chunks "
                f"(added {s['ingested_at'][:10]})"
            )
        return "\n".join(lines)
    except Exception as exc:
        return _recover("list_documents", exc)


def delete_document(source: str) -> str:
    """Remove a document and all its embeddings."""
    if not _pg_available():
        return "[delete_document] Unavailable — DATABASE_URL not set."
    try:
        from rag.store import delete_source
        count = delete_source(source)
        if count == 0:
            return (
                f"No document found with source '{source}'. "
                "Use list_documents to see exact filenames."
            )
        return f"Deleted {count} chunks for '{source}'."
    except Exception as exc:
        return _recover("delete_document", exc)
