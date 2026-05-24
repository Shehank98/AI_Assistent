"""
rag/ingest.py — Document loaders for Jarvis knowledge base.
Supports: Excel (.xlsx/.xls), CSV, PDF, plain text/markdown.
All formats are chunked and stored via rag.store.
"""

from pathlib import Path


def _chunk_text(
    text: str,
    source: str,
    metadata: dict,
    chunk_size: int = 400,
    overlap: int = 40,
) -> list[dict]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + chunk_size]
        content = " ".join(chunk_words).strip()
        if content:
            chunks.append({"content": content, "source": source, "metadata": metadata})
        i += chunk_size - overlap
        if i >= len(words):
            break
    return chunks


def ingest_excel(file_path: str) -> int:
    """Chunk an Excel workbook by sheet + row ranges. Returns chunk count."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("pip install openpyxl")

    from . import store

    wb = openpyxl.load_workbook(file_path, data_only=True)
    source = Path(file_path).name
    all_chunks = []
    ROWS_PER_CHUNK = 25

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        # Treat first row as headers
        headers = [
            str(c).strip() if c is not None else f"col_{i}"
            for i, c in enumerate(rows[0])
        ]

        for start in range(1, len(rows), ROWS_PER_CHUNK):
            batch = rows[start : start + ROWS_PER_CHUNK]
            lines = []
            for row_idx, row in enumerate(batch):
                parts = [
                    f"{headers[i]}: {v}"
                    for i, v in enumerate(row)
                    if v is not None and str(v).strip()
                ]
                if parts:
                    lines.append(
                        f"Row {start + row_idx + 1}: " + " | ".join(parts)
                    )
            if lines:
                all_chunks.append(
                    {
                        "content": "\n".join(lines),
                        "source": source,
                        "metadata": {
                            "file": source,
                            "sheet": sheet_name,
                            "row_start": start + 1,
                            "row_end": start + len(batch),
                        },
                    }
                )

    return store.add_chunks(all_chunks)


def ingest_csv(file_path: str) -> int:
    """Chunk a CSV file by row ranges. Returns chunk count."""
    import csv
    from . import store

    source = Path(file_path).name
    all_chunks = []
    ROWS_PER_CHUNK = 30

    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for start in range(0, len(rows), ROWS_PER_CHUNK):
        batch = rows[start : start + ROWS_PER_CHUNK]
        lines = [
            f"Row {start + i + 1}: "
            + " | ".join(f"{k}: {v}" for k, v in row.items() if v and str(v).strip())
            for i, row in enumerate(batch)
        ]
        lines = [l for l in lines if l.strip()]
        if lines:
            all_chunks.append(
                {
                    "content": "\n".join(lines),
                    "source": source,
                    "metadata": {
                        "file": source,
                        "row_start": start + 1,
                        "row_end": start + len(batch),
                    },
                }
            )

    return store.add_chunks(all_chunks)


def ingest_pdf(file_path: str) -> int:
    """Extract text from PDF and chunk it. Returns chunk count."""
    from . import store

    source = Path(file_path).name
    text = ""

    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except ImportError:
        try:
            import fitz
            doc = fitz.open(file_path)
            text = "\n".join(page.get_text() for page in doc)
        except ImportError:
            raise ImportError(
                "Install a PDF library: pip install pdfplumber   or   pip install PyMuPDF"
            )

    chunks = _chunk_text(text, source=source, metadata={"file": source, "type": "pdf"})
    return store.add_chunks(chunks)


def ingest_text(file_path: str) -> int:
    """Chunk a plain text / markdown file. Returns chunk count."""
    from . import store

    source = Path(file_path).name
    text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    ext = Path(file_path).suffix.lower().lstrip(".")
    chunks = _chunk_text(text, source=source, metadata={"file": source, "type": ext or "text"})
    return store.add_chunks(chunks)


def ingest_file(file_path: str) -> tuple[int, str]:
    """
    Auto-detect format and ingest a file into the RAG store.
    Returns (chunk_count, format_name).
    """
    ext = Path(file_path).suffix.lower()

    if ext in (".xlsx", ".xls", ".xlsm", ".xlsb"):
        return ingest_excel(file_path), "excel"
    elif ext == ".csv":
        return ingest_csv(file_path), "csv"
    elif ext == ".pdf":
        return ingest_pdf(file_path), "pdf"
    elif ext in (".txt", ".md", ".rst", ".log"):
        return ingest_text(file_path), "text"
    else:
        # Attempt as plain text for unknown types
        try:
            return ingest_text(file_path), "text"
        except Exception as e:
            raise ValueError(f"Unsupported file type '{ext}': {e}")
