"""
tools/registry.py — All Jarvis tools + dispatcher
Add new tools here; they're automatically available to Claude.
"""

import os
import subprocess
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

# ── Tool Definitions (Claude's API format) ────────────────────────────────────
TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file from disk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or overwrite a file on disk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string", "description": "Text content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: current dir)"}
            },
            "required": [],
        },
    },
    {
        "name": "run_shell",
        "description": "Run a shell command and return stdout/stderr. Use for opening apps, running scripts, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo and return top results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name (e.g. 'Colombo')"}
            },
            "required": ["city"],
        },
    },
    {
        "name": "remember_fact",
        "description": "Save a fact about the user for future sessions (e.g. preferences, name, habits).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Fact label (e.g. 'favorite_coffee')"},
                "value": {"type": "string", "description": "The fact value"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "recall_facts",
        "description": "Retrieve all remembered facts about the user.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_datetime",
        "description": "Get the current date and time.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "open_url",
        "description": "Open a URL in the default web browser.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to open"}
            },
            "required": ["url"],
        },
    },
]


# ── Tool Implementations ───────────────────────────────────────────────────────

def _read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def _list_directory(path: str = ".") -> str:
    try:
        entries = list(Path(path).iterdir())
        lines = [f"{'[DIR] ' if e.is_dir() else '      '}{e.name}" for e in sorted(entries)]
        return "\n".join(lines) or "(empty)"
    except Exception as e:
        return f"Error: {e}"


def _run_shell(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        parts = []
        if out:
            parts.append(f"STDOUT:\n{out}")
        if err:
            parts.append(f"STDERR:\n{err}")
        parts.append(f"Exit code: {result.returncode}")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error: {e}"


def _web_search(query: str) -> str:
    """DuckDuckGo Instant Answer API (no key needed)."""
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
        return "\n".join(results) if results else "No instant answer found. Try a more specific query."
    except Exception as e:
        return f"Search error: {e}"


def _get_weather(city: str) -> str:
    """Uses wttr.in (no API key needed)."""
    try:
        encoded = urllib.parse.quote_plus(city)
        url = f"https://wttr.in/{encoded}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        current = data["current_condition"][0]
        desc = current["weatherDesc"][0]["value"]
        temp_c = current["temp_C"]
        feels = current["FeelsLikeC"]
        humidity = current["humidity"]
        return (
            f"{city}: {desc}, {temp_c}°C (feels like {feels}°C), "
            f"Humidity: {humidity}%"
        )
    except Exception as e:
        return f"Weather error: {e}"


def _get_datetime() -> str:
    return datetime.now().strftime("%A, %B %d %Y — %I:%M %p")


def _open_url(url: str) -> str:
    try:
        import webbrowser
        webbrowser.open(url)
        return f"Opened {url} in browser."
    except Exception as e:
        return f"Error: {e}"


# Memory backed by the MemoryStore imported in jarvis.py
# These are shims that the dispatcher calls; memory object passed in separately.
_memory_store = None

def _remember_fact(key: str, value: str) -> str:
    if _memory_store:
        _memory_store.save_fact(key, value)
        return f"Remembered: {key} = {value}"
    return "Memory not initialised."

def _recall_facts() -> str:
    if _memory_store:
        facts = _memory_store.get_all_facts()
        if not facts:
            return "No facts stored yet."
        return "\n".join(f"{k}: {v}" for k, v in facts.items())
    return "Memory not initialised."


# ── Dispatcher ────────────────────────────────────────────────────────────────
TOOL_MAP = {
    "read_file": lambda inp: _read_file(inp["path"]),
    "write_file": lambda inp: _write_file(inp["path"], inp["content"]),
    "list_directory": lambda inp: _list_directory(inp.get("path", ".")),
    "run_shell": lambda inp: _run_shell(inp["command"], inp.get("timeout", 30)),
    "web_search": lambda inp: _web_search(inp["query"]),
    "get_weather": lambda inp: _get_weather(inp["city"]),
    "get_datetime": lambda inp: _get_datetime(),
    "open_url": lambda inp: _open_url(inp["url"]),
    "remember_fact": lambda inp: _remember_fact(inp["key"], inp["value"]),
    "recall_facts": lambda inp: _recall_facts(),
}


def handle_tool_call(name: str, inputs: dict) -> str:
    handler = TOOL_MAP.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    try:
        return handler(inputs)
    except Exception as e:
        return f"Tool '{name}' error: {e}"


def set_memory_store(store):
    """Called by jarvis.py to wire up the memory store to tools."""
    global _memory_store
    _memory_store = store
