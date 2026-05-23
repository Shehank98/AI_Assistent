"""
tools/web_tool.py — Web search, fetch, YouTube, Wikipedia.
All free — no API keys needed.
"""

import json
import urllib.parse
import urllib.request


def web_search(query: str) -> str:
    """DuckDuckGo instant answer search (no API key needed)."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_redirect=1&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())

        results = []
        if data.get("AbstractText"):
            results.append(f"Summary: {data['AbstractText']}")
        for item in data.get("RelatedTopics", [])[:5]:
            if isinstance(item, dict) and item.get("Text"):
                results.append(f"• {item['Text']}")
        return "\n".join(results) if results else "No instant answer. Try a more specific query."
    except Exception as e:
        return f"Search error: {e}"


def web_fetch(url: str) -> str:
    """Fetch and extract readable text from any URL."""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return f"Could not fetch: {url}"
        text = trafilatura.extract(downloaded)
        if not text:
            return f"Could not extract text from: {url}"
        return text[:4000]
    except ImportError:
        # Fallback: raw urllib
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                content = r.read().decode("utf-8", errors="replace")
            import re
            # Strip tags crudely
            text = re.sub(r"<[^>]+>", " ", content)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:3000]
        except Exception as e2:
            return f"Fetch error: {e2}"
    except Exception as e:
        return f"Fetch error: {e}"


def youtube_search(query: str) -> str:
    """Return top 3 YouTube results with title + URL. No API key needed."""
    try:
        from youtubesearchpython import VideosSearch
        search = VideosSearch(query, limit=3)
        results = search.result().get("result", [])
        if not results:
            return f"No YouTube results for: {query}"
        lines = []
        for r in results:
            title = r.get("title", "?")
            link = r.get("link", "?")
            duration = r.get("duration", "")
            lines.append(f"• {title} [{duration}]\n  {link}")
        return "\n\n".join(lines)
    except ImportError:
        return "youtube-search-python not installed. Run: pip install youtube-search-python"
    except Exception as e:
        return f"YouTube search error: {e}"


def wikipedia(query: str) -> str:
    """Get a Wikipedia summary for a topic."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        extract = data.get("extract", "")
        title = data.get("title", query)
        if not extract:
            return f"No Wikipedia article found for: {query}"
        return f"**{title}**\n{extract[:1500]}"
    except Exception as e:
        return f"Wikipedia error: {e}"
