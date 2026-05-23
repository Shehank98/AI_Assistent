"""
tools/github_tool.py — GitHub integration via REST API.
Requires GITHUB_TOKEN environment variable (Settings → Developer settings → Personal access tokens).
"""

import json
import os
import urllib.request
import urllib.parse

_BASE = "https://api.github.com"
_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Jarvis/1.0",
    }
    if _TOKEN:
        h["Authorization"] = f"Bearer {_TOKEN}"
    return h


def _get(path: str) -> dict | list:
    req = urllib.request.Request(f"{_BASE}{path}", headers=_headers())
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _post(path: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{_BASE}{path}", data=body,
                                  headers={**_headers(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _need_token() -> str | None:
    if not _TOKEN:
        return "GITHUB_TOKEN not set. Add it in Railway → Variables."
    return None


def github_search(query: str, type_: str = "repositories") -> str:
    """Search GitHub repos, code, or issues."""
    err = _need_token()
    if err:
        return err
    try:
        data = _get(f"/search/{type_}?q={urllib.parse.quote(query)}&per_page=5")
        items = data.get("items", [])
        if not items:
            return f"No GitHub {type_} found for '{query}'."
        lines = []
        for item in items:
            if type_ == "repositories":
                stars = item.get("stargazers_count", 0)
                desc = (item.get("description") or "")[:70]
                lines.append(f"⭐{stars:,}  {item['full_name']}  —  {desc}")
            else:
                lines.append(f"[{item.get('state', '')}] {item.get('title', item.get('path', ''))}")
        return "\n".join(lines)
    except Exception as e:
        return f"GitHub search error: {e}"


def github_create_issue(repo: str, title: str, body: str = "") -> str:
    """Create a GitHub issue. repo format: 'owner/repo'."""
    err = _need_token()
    if err:
        return err
    try:
        result = _post(f"/repos/{repo}/issues", {"title": title, "body": body})
        return f"Issue #{result['number']} created: {result['html_url']}"
    except Exception as e:
        return f"GitHub issue error: {e}"


def github_my_repos() -> str:
    """List your GitHub repositories (most recently pushed)."""
    err = _need_token()
    if err:
        return err
    try:
        repos = _get("/user/repos?sort=pushed&per_page=10")
        if not repos:
            return "No repositories found."
        lines = [
            f"[{r.get('pushed_at','')[:10]}] {r['full_name']}"
            + (" ⭐" if r.get("stargazers_count", 0) else "")
            for r in repos
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"GitHub repos error: {e}"
