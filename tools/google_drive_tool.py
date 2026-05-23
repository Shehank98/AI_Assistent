"""
tools/google_drive_tool.py — Google Drive search and read.
Requires 'drive.readonly' scope (+ 'drive.file' to create docs).
"""

from datetime import datetime, timedelta


def _svc():
    from tools.google_auth import get_service
    return get_service("drive", "v3")


def drive_search(query: str, max_results: int = 8) -> str:
    """Search Drive files by name or content."""
    try:
        safe_q = query.replace("'", "\\'")
        result = _svc().files().list(
            q=f"(fullText contains '{safe_q}' or name contains '{safe_q}') and trashed=false",
            fields="files(id,name,mimeType,modifiedTime)",
            pageSize=max_results,
            orderBy="modifiedTime desc",
        ).execute()
        files = result.get("files", [])
        if not files:
            return f"No Drive files found for '{query}'."
        lines = []
        for f in files:
            modified = f.get("modifiedTime", "")[:10]
            kind = f["mimeType"].split(".")[-1].replace("application-", "")
            lines.append(f"[{modified}] {f['name']}  ({kind})  ID:{f['id'][:10]}…")
        return "\n".join(lines)
    except Exception as e:
        return _scope_err(e)


def drive_read(file_id: str) -> str:
    """Read content of a Google Doc or text file by ID."""
    try:
        svc = _svc()
        meta = svc.files().get(fileId=file_id, fields="name,mimeType").execute()
        mime = meta.get("mimeType", "")
        name = meta.get("name", file_id)

        if "document" in mime:
            raw = svc.files().export(fileId=file_id, mimeType="text/plain").execute()
            text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        elif "spreadsheet" in mime:
            return f"Use sheets_read for Google Sheets. File ID: {file_id}"
        else:
            raw = svc.files().get_media(fileId=file_id).execute()
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)

        return f"[{name}]\n\n{text[:8000]}"
    except Exception as e:
        return _scope_err(e)


def drive_list_recent(days: int = 7) -> str:
    """List Drive files modified in the last N days."""
    try:
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = _svc().files().list(
            q=f"modifiedTime > '{cutoff}' and trashed=false",
            fields="files(id,name,mimeType,modifiedTime)",
            pageSize=15,
            orderBy="modifiedTime desc",
        ).execute()
        files = result.get("files", [])
        if not files:
            return f"No Drive files modified in the last {days} days."
        lines = [f"[{f['modifiedTime'][:10]}] {f['name']}  ID:{f['id'][:10]}…" for f in files]
        return "\n".join(lines)
    except Exception as e:
        return _scope_err(e)


def drive_create_doc(title: str, content: str) -> str:
    """Create a new Google Doc with content."""
    try:
        from tools.google_auth import get_service
        docs = get_service("docs", "v1")
        doc = docs.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
        ).execute()
        return f"Created Google Doc '{title}'\nID: {doc_id}\nhttps://docs.google.com/document/d/{doc_id}"
    except Exception as e:
        return _scope_err(e)


def _scope_err(e: Exception) -> str:
    msg = str(e).lower()
    if "insufficient" in msg or "permission" in msg or "403" in msg:
        return ("Drive needs 'drive.readonly' scope. "
                "Re-run auth/google_oauth.py to grant it.")
    return f"Drive error: {e}"
