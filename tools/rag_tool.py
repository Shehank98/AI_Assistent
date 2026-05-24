"""
tools/rag_tool.py — RAG (document search) tools for Jarvis.
Requires DATABASE_URL pointing to a PostgreSQL DB with pgvector enabled.
"""

import os


def _available() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def query_docs(query: str, k: int = 5, source: str = "") -> str:
    """Semantic search across all uploaded documents and spreadsheets."""
    if not _available():
        return "Document search unavailable — needs PostgreSQL (DATABASE_URL not set)."
    try:
        from rag.store import search
        results = search(query, k=k, source_filter=source)
        if not results:
            return "No relevant content found in the knowledge base. Upload files at /api/upload."

        lines = [f"Found {len(results)} relevant passage(s) for: '{query}'\n"]
        for i, r in enumerate(results, 1):
            meta = r.get("metadata") or {}
            pct = int(r["score"] * 100)
            loc = r.get("source", "")
            if meta.get("sheet"):
                loc += f" / {meta['sheet']} rows {meta.get('row_start','?')}–{meta.get('row_end','?')}"
            lines.append(f"[{i}] {pct}% match — {loc}\n{r['content'][:500]}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Document search error: {e}"


def list_documents() -> str:
    """List all documents/spreadsheets indexed in the knowledge base."""
    if not _available():
        return "Document store unavailable — DATABASE_URL not set."
    try:
        from rag.store import list_sources
        sources = list_sources()
        if not sources:
            return "No documents indexed yet. Upload a file at /api/upload or say 'upload a file'."
        lines = ["Indexed documents:"]
        for s in sources:
            lines.append(f"  • {s['source']} — {s['chunks']} chunks (added {s['ingested_at'][:10]})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def delete_document(source: str) -> str:
    """Remove a document and all its embeddings from the knowledge base."""
    if not _available():
        return "Document store unavailable."
    try:
        from rag.store import delete_source
        count = delete_source(source)
        if count == 0:
            return f"No document found with source '{source}'. Use list_documents to check exact names."
        return f"Deleted {count} chunks for '{source}'."
    except Exception as e:
        return f"Error: {e}"
