"""
rag/embeddings.py — Gemini REST embedding (v1 stable endpoint, not v1beta).

The google-genai SDK defaults to v1beta which doesn't expose text-embedding-004.
We call the stable v1 REST API directly to avoid that routing issue.
"""

import json
import os
import urllib.error
import urllib.request

EMBED_MODEL = "text-embedding-004"
EMBEDDING_DIM = 768
_API_BASE = "https://generativelanguage.googleapis.com/v1"

# Alternative models to try if primary fails (same 768-dim family)
_FALLBACK_MODELS = [
    "text-embedding-004",
    "embedding-001",
]


def embed_text(text: str) -> list[float]:
    """Embed a single string. Returns 768 floats. Self-heals across model names."""
    text = text.strip()
    if not text:
        return [0.0] * EMBEDDING_DIM

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set — cannot embed.")

    # Truncate to avoid hitting input token limits
    text = text[:8000]

    last_error = None
    for model in _FALLBACK_MODELS:
        try:
            return _call_embed_api(text, model, api_key)
        except RuntimeError as e:
            last_error = e
            continue

    raise RuntimeError(
        f"All embedding models failed. Last error: {last_error}\n"
        "Check GEMINI_API_KEY is valid and has Gemini API access."
    )


def _call_embed_api(text: str, model: str, api_key: str) -> list[float]:
    url = f"{_API_BASE}/models/{model}:embedContent?key={api_key}"
    payload = json.dumps({
        "model": f"models/{model}",
        "content": {"parts": [{"text": text}]},
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        values = data.get("embedding", {}).get("values", [])
        if not values:
            raise RuntimeError(f"Empty embedding returned by {model}")
        return values
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} from {model}: {body[:300]}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error reaching Gemini API: {exc.reason}")


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts sequentially."""
    return [embed_text(t) for t in texts]
