"""
rag/embeddings.py — Gemini text embeddings (no OpenAI key needed).
Uses text-embedding-004 (768 dimensions, free tier available).
"""

import os

_client = None
EMBED_MODEL = "models/text-embedding-004"
EMBEDDING_DIM = 768


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
    return _client


def embed_text(text: str) -> list[float]:
    """Embed a single string. Returns a list of 768 floats."""
    text = text.strip()
    if not text:
        return [0.0] * EMBEDDING_DIM
    result = _get_client().models.embed_content(
        model=EMBED_MODEL,
        contents=text,
    )
    if result.embeddings:
        return list(result.embeddings[0].values)
    raise ValueError("Empty embedding response from Gemini")


def embed_batch(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """Embed a list of texts in batches. Returns list of embedding vectors."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        for text in batch:
            all_embeddings.append(embed_text(text))
    return all_embeddings
