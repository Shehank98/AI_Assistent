"""
tools/news_tool.py — News headlines via NewsAPI (with RSS fallback).
NEWS_API_KEY env var is optional — falls back to free RSS feeds if not set.
"""

import json
import os
import urllib.parse
import urllib.request

NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

# Free RSS fallbacks (no API key needed)
RSS_FEEDS = {
    "general": "https://feeds.bbci.co.uk/news/rss.xml",
    "tech": "https://feeds.feedburner.com/TechCrunch",
    "world": "https://feeds.reuters.com/reuters/worldNews",
    "business": "https://feeds.bbci.co.uk/news/business/rss.xml",
}


def _newsapi_headlines(category: str = "general", country: str = "lk") -> list[dict]:
    url = (
        f"https://newsapi.org/v2/top-headlines?"
        f"category={category}&country={country}&pageSize=5&apiKey={NEWS_API_KEY}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    return data.get("articles", [])


def _rss_headlines(feed_url: str, limit: int = 5) -> list[dict]:
    try:
        import feedparser
        feed = feedparser.parse(feed_url)
        return [
            {"title": e.get("title", ""), "source": {"name": feed.feed.get("title", "RSS")},
             "description": e.get("summary", "")[:200]}
            for e in feed.entries[:limit]
        ]
    except ImportError:
        # feedparser not installed — try raw urllib
        req = urllib.request.Request(feed_url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8", errors="replace")
        import re
        titles = re.findall(r"<title><!\[CDATA\[([^\]]+)\]\]></title>", content)
        titles = titles or re.findall(r"<title>([^<]+)</title>", content)
        titles = [t for t in titles if t.strip() and "rss" not in t.lower()][:limit]
        return [{"title": t, "source": {"name": "RSS"}, "description": ""} for t in titles]


def _fmt_articles(articles: list[dict]) -> str:
    lines = []
    for a in articles:
        source = a.get("source", {}).get("name", "")
        title = a.get("title", "")
        desc = a.get("description", "") or ""
        desc = desc[:100].rstrip()
        lines.append(f"• [{source}] {title}\n  {desc}")
    return "\n\n".join(lines)


def news_headlines(category: str = "general", country: str = "lk") -> str:
    """Top 5 headlines — uses NewsAPI if key set, else BBC RSS."""
    try:
        if NEWS_API_KEY:
            articles = _newsapi_headlines(category, country)
        else:
            feed_url = RSS_FEEDS.get(category, RSS_FEEDS["general"])
            articles = _rss_headlines(feed_url)
        if not articles:
            return "No headlines found."
        return _fmt_articles(articles)
    except Exception as e:
        return f"News error: {e}"


def news_search(query: str) -> str:
    """Search news by topic."""
    try:
        if NEWS_API_KEY:
            url = (
                f"https://newsapi.org/v2/everything?"
                f"q={urllib.parse.quote_plus(query)}&pageSize=5&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            articles = data.get("articles", [])
        else:
            # DuckDuckGo news fallback
            encoded = urllib.parse.quote_plus(query)
            url = f"https://api.duckduckgo.com/?q={encoded}+news&format=json&no_redirect=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            topics = data.get("RelatedTopics", [])[:5]
            articles = [{"title": t.get("Text", ""), "source": {"name": "DDG"},
                         "description": ""} for t in topics if isinstance(t, dict) and t.get("Text")]

        if not articles:
            return f"No news found for: {query}"
        return _fmt_articles(articles)
    except Exception as e:
        return f"News search error: {e}"


def news_tech() -> str:
    """Tech news — TechCrunch RSS (always free)."""
    try:
        articles = _rss_headlines(RSS_FEEDS["tech"])
        if not articles:
            return "No tech news found."
        return _fmt_articles(articles)
    except Exception as e:
        return f"Tech news error: {e}"
