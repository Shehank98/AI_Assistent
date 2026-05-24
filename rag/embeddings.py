"""
rag/embeddings.py — Gemini REST embedding with automatic version/model fallback.

Tries all combinations of API version + model until one works,
because Google moves models between v1 and v1beta without notice.
"""

import json
import os
import urllib.error
import urllib.request

EMBEDDING_DIM = 768
_API_ROOT = "https://generativelanguage.googleapis.com"

# Ordered list of (api_version, model) to try — first success wins
_CANDIDATES = [
    ("v1beta", "text-embedding-004"),
    ("v1",     "text-embedding-004"),
    ("v1beta", "embedding-001"),
    ("v1",     "embedding-001"),
]


def embed_text(text: str) -> list[float]:
    """Embed a single string. Returns 768 floats. Tries all API version/model combos."""
    text = text.strip()
    if not text:
        return [0.0] * EMBEDDING_DIM

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set — cannot embed.")

    text = text[:8000]

    last_error = None
    for api_ver, model in _CANDIDATES:
        try:
            return _call_embed_api(text, model, api_ver, api_key)
        except RuntimeError as e:
            last_error = e
            continue

    raise RuntimeError(
        f"All embedding attempts failed. Last error: {last_error}\n"
        "Check GEMINI_API_KEY is valid and has Gemini API access at aistudio.google.com."
    )


def _call_embed_api(text: str, model: str, api_ver: str, api_key: str) -> list[float]:
    url = f"{_API_ROOT}/{api_ver}/models/{model}:embedContent?key={api_key}"
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
            raise RuntimeError(f"Empty embedding returned by {api_ver}/{model}")
        return values
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} from {api_ver}/{model}: {body[:300]}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error reaching Gemini API: {exc.reason}")


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts sequentially."""
    return [embed_text(t) for t in texts]
