"""
tools/registry.py — Central tool registry for Jarvis.
All tools exposed to Claude are defined and dispatched here.
Desktop-only tools are excluded when DESKTOP_MODE != "true".
"""

import os

DESKTOP_MODE = os.environ.get("DESKTOP_MODE", "false").lower() == "true"

# ── Memory store wiring ────────────────────────────────────────────────────────
_memory_store = None


def set_memory_store(store):
    """Called by Jarvis.__init__ to wire the memory store to all memory tools."""
    global _memory_store
    _memory_store = store
    from tools.memory_tool import set_store
    set_store(store)


# ── Tool Definitions ───────────────────────────────────────────────────────────

_TOOLS_BASE = [
    # ── Web / Search ──────────────────────────────────────────────────────────
    {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo. Returns instant answers and related topics.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch and extract readable text from any URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Full URL to fetch"}},
            "required": ["url"],
        },
    },
    {
        "name": "youtube_search",
        "description": "Search YouTube and return top 3 results with titles and links.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "wikipedia",
        "description": "Get a Wikipedia summary for a topic or person.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },

    # ── System / Utilities ────────────────────────────────────────────────────
    {
        "name": "get_weather",
        "description": "Get current weather for a city. Defaults to JARVIS_LOCATION if city not given.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name (optional)"}},
            "required": [],
        },
    },
    {
        "name": "get_datetime",
        "description": "Get the current date and time.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_timer",
        "description": "Set a countdown timer that alerts when time is up.",
        "input_schema": {
            "type": "object",
            "properties": {
                "duration_seconds": {"type": "integer", "description": "Duration in seconds"},
                "label": {"type": "string", "description": "What the timer is for"},
            },
            "required": ["duration_seconds"],
        },
    },
    {
        "name": "create_note",
        "description": "Save a note to ~/Notes/ as a markdown file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "list_notes",
        "description": "List all saved notes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_note",
        "description": "Read a saved note by title (partial match ok).",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file from disk.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or create a file on disk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
            "required": [],
        },
    },

    # ── Memory ────────────────────────────────────────────────────────────────
    {
        "name": "remember",
        "description": "Save a fact about Shehan for future sessions (e.g. preferences, habits).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Fact label"},
                "value": {"type": "string", "description": "Fact value"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "recall",
        "description": "Retrieve a specific remembered fact by key.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "recall_all",
        "description": "Return everything Jarvis knows about Shehan.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "forget",
        "description": "Delete a remembered fact.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "add_task",
        "description": "Add a task to the task list with optional due date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "due_date": {"type": "string", "description": "YYYY-MM-DD (optional)"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "list_tasks",
        "description": "List all pending tasks.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "complete_task",
        "description": "Mark a task as done by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "list_tasks_due_today",
        "description": "List tasks due today.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },

    # ── Gmail ─────────────────────────────────────────────────────────────────
    {
        "name": "gmail_unread",
        "description": "Get unread emails. Flags [person] vs [auto] (newsletters/automated).",
        "input_schema": {
            "type": "object",
            "properties": {"max_results": {"type": "integer", "description": "Max emails (default 15)"}},
            "required": [],
        },
    },
    {
        "name": "gmail_search",
        "description": "Search Gmail by any query string (e.g. 'from:boss@company.com', 'subject:invoice').",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "gmail_read_full",
        "description": "Read the full body of an email by ID (use the ID from gmail_unread/gmail_search).",
        "input_schema": {
            "type": "object",
            "properties": {"email_id": {"type": "string"}},
            "required": ["email_id"],
        },
    },
    {
        "name": "gmail_send",
        "description": "Send an email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "gmail_reply",
        "description": "Reply to an email thread by email ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["email_id", "body"],
        },
    },
    {
        "name": "gmail_mark_read",
        "description": "Mark an email as read by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"email_id": {"type": "string"}},
            "required": ["email_id"],
        },
    },
    {
        "name": "gmail_important_check",
        "description": "Check for emails from real people (not automated) in the last 24h.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },

    # ── Calendar ──────────────────────────────────────────────────────────────
    {
        "name": "calendar_today",
        "description": "Get all events on the calendar today.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calendar_tomorrow",
        "description": "Get tomorrow's calendar events.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calendar_week",
        "description": "Get events for the next 7 days, grouped by day.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calendar_upcoming",
        "description": "Get events starting within N minutes (default 30).",
        "input_schema": {
            "type": "object",
            "properties": {"minutes": {"type": "integer", "description": "Look-ahead window in minutes"}},
            "required": [],
        },
    },
    {
        "name": "calendar_create",
        "description": "Create a calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM (24h)"},
                "duration_minutes": {"type": "integer", "description": "Duration (default 60)"},
                "description": {"type": "string"},
            },
            "required": ["title", "date", "time"],
        },
    },
    {
        "name": "calendar_delete",
        "description": "Delete a calendar event by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"event_id": {"type": "string"}},
            "required": ["event_id"],
        },
    },

    # ── Spotify ───────────────────────────────────────────────────────────────
    {
        "name": "spotify_play",
        "description": "Search and play a song, artist, or playlist on Spotify.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Song name, artist, or playlist"}},
            "required": ["query"],
        },
    },
    {
        "name": "spotify_pause",
        "description": "Pause Spotify playback.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "spotify_resume",
        "description": "Resume Spotify playback.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "spotify_next",
        "description": "Skip to the next track on Spotify.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "spotify_current",
        "description": "What is currently playing on Spotify.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "spotify_volume",
        "description": "Set Spotify volume (0-100).",
        "input_schema": {
            "type": "object",
            "properties": {"level": {"type": "integer", "description": "Volume 0-100"}},
            "required": ["level"],
        },
    },
    {
        "name": "spotify_queue",
        "description": "Add a song to the Spotify queue.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },

    # ── News ──────────────────────────────────────────────────────────────────
    {
        "name": "news_headlines",
        "description": "Get top headlines. category: general/tech/world/business. country: lk/us/gb/etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "general|tech|world|business"},
                "country": {"type": "string", "description": "Country code (default: lk)"},
            },
            "required": [],
        },
    },
    {
        "name": "news_search",
        "description": "Search news by topic or keyword.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "news_tech",
        "description": "Get latest tech news (TechCrunch).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# Desktop-only tools (excluded on Railway)
_TOOLS_DESKTOP = [
    {
        "name": "open_url",
        "description": "Open a URL in the default browser. Desktop only.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "run_shell",
        "description": "Execute a shell command and return output. Desktop only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "description": "Timeout seconds (default 30)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "whatsapp_send",
        "description": "Send a WhatsApp message. Desktop only — requires WhatsApp Web logged in.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "International format: +94771234567"},
                "message": {"type": "string"},
            },
            "required": ["phone_number", "message"],
        },
    },
    {
        "name": "whatsapp_send_to_contact",
        "description": "Send WhatsApp to a saved contact by name. Desktop only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Contact name (partial match ok)"},
                "message": {"type": "string"},
            },
            "required": ["name", "message"],
        },
    },
]

TOOLS = _TOOLS_BASE + (_TOOLS_DESKTOP if DESKTOP_MODE else [])


# ── Dispatcher ────────────────────────────────────────────────────────────────

def handle_tool_call(name: str, inputs: dict) -> str:
    from tools import memory_tool, web_tool, system_tool, news_tool

    # Lazy imports for optional tool modules
    def _try_import(module_name):
        try:
            import importlib
            return importlib.import_module(f"tools.{module_name}")
        except Exception:
            return None

    # ── Web
    if name == "web_search":
        return web_tool.web_search(inputs["query"])
    if name == "web_fetch":
        return web_tool.web_fetch(inputs["url"])
    if name == "youtube_search":
        return web_tool.youtube_search(inputs["query"])
    if name == "wikipedia":
        return web_tool.wikipedia(inputs["query"])

    # ── System
    if name == "get_weather":
        return system_tool.get_weather(inputs.get("city", ""))
    if name == "get_datetime":
        return system_tool.get_datetime()
    if name == "set_timer":
        return system_tool.set_timer(inputs["duration_seconds"], inputs.get("label", "Timer"))
    if name == "create_note":
        return system_tool.create_note(inputs["title"], inputs["content"])
    if name == "list_notes":
        return system_tool.list_notes()
    if name == "read_note":
        return system_tool.read_note(inputs["title"])
    if name == "read_file":
        from pathlib import Path
        try:
            return Path(inputs["path"]).read_text(encoding="utf-8")
        except Exception as e:
            return f"Error: {e}"
    if name == "write_file":
        from pathlib import Path
        try:
            p = Path(inputs["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(inputs["content"], encoding="utf-8")
            return f"Written to {inputs['path']}"
        except Exception as e:
            return f"Error: {e}"
    if name == "list_directory":
        from pathlib import Path
        try:
            entries = list(Path(inputs.get("path", ".")).iterdir())
            lines = [f"{'[DIR] ' if e.is_dir() else '      '}{e.name}" for e in sorted(entries)]
            return "\n".join(lines) or "(empty)"
        except Exception as e:
            return f"Error: {e}"
    if name == "open_url":
        return system_tool.open_url(inputs["url"])
    if name == "run_shell":
        return system_tool.run_shell(inputs["command"], inputs.get("timeout", 30))

    # ── Memory
    if name == "remember":
        return memory_tool.remember(inputs["key"], inputs["value"])
    if name == "recall":
        return memory_tool.recall(inputs["key"])
    if name == "recall_all":
        return memory_tool.recall_all()
    if name == "forget":
        return memory_tool.forget(inputs["key"])
    if name == "add_task":
        return memory_tool.add_task(inputs["task"], inputs.get("due_date", ""))
    if name == "list_tasks":
        return memory_tool.list_tasks()
    if name == "complete_task":
        return memory_tool.complete_task(inputs["task_id"])
    if name == "list_tasks_due_today":
        return memory_tool.list_tasks_due_today()

    # ── Gmail
    if name == "gmail_unread":
        m = _try_import("gmail_tool")
        return m.gmail_unread(inputs.get("max_results", 15)) if m else "Gmail not available."
    if name == "gmail_search":
        m = _try_import("gmail_tool")
        return m.gmail_search(inputs["query"]) if m else "Gmail not available."
    if name == "gmail_read_full":
        m = _try_import("gmail_tool")
        return m.gmail_read_full(inputs["email_id"]) if m else "Gmail not available."
    if name == "gmail_send":
        m = _try_import("gmail_tool")
        return m.gmail_send(inputs["to"], inputs["subject"], inputs["body"]) if m else "Gmail not available."
    if name == "gmail_reply":
        m = _try_import("gmail_tool")
        return m.gmail_reply(inputs["email_id"], inputs["body"]) if m else "Gmail not available."
    if name == "gmail_mark_read":
        m = _try_import("gmail_tool")
        return m.gmail_mark_read(inputs["email_id"]) if m else "Gmail not available."
    if name == "gmail_important_check":
        m = _try_import("gmail_tool")
        return m.gmail_important_check() if m else "Gmail not available."

    # ── Calendar
    if name == "calendar_today":
        m = _try_import("calendar_tool")
        return m.calendar_today() if m else "Calendar not available."
    if name == "calendar_tomorrow":
        m = _try_import("calendar_tool")
        return m.calendar_tomorrow() if m else "Calendar not available."
    if name == "calendar_week":
        m = _try_import("calendar_tool")
        return m.calendar_week() if m else "Calendar not available."
    if name == "calendar_upcoming":
        m = _try_import("calendar_tool")
        return m.calendar_upcoming(inputs.get("minutes", 30)) if m else "Calendar not available."
    if name == "calendar_create":
        m = _try_import("calendar_tool")
        return m.calendar_create(inputs["title"], inputs["date"], inputs["time"],
                                  inputs.get("duration_minutes", 60),
                                  inputs.get("description", "")) if m else "Calendar not available."
    if name == "calendar_delete":
        m = _try_import("calendar_tool")
        return m.calendar_delete(inputs["event_id"]) if m else "Calendar not available."

    # ── Spotify
    if name == "spotify_play":
        m = _try_import("spotify_tool")
        return m.spotify_play(inputs["query"]) if m else "Spotify not available."
    if name == "spotify_pause":
        m = _try_import("spotify_tool")
        return m.spotify_pause() if m else "Spotify not available."
    if name == "spotify_resume":
        m = _try_import("spotify_tool")
        return m.spotify_resume() if m else "Spotify not available."
    if name == "spotify_next":
        m = _try_import("spotify_tool")
        return m.spotify_next() if m else "Spotify not available."
    if name == "spotify_current":
        m = _try_import("spotify_tool")
        return m.spotify_current() if m else "Spotify not available."
    if name == "spotify_volume":
        m = _try_import("spotify_tool")
        return m.spotify_volume(inputs["level"]) if m else "Spotify not available."
    if name == "spotify_queue":
        m = _try_import("spotify_tool")
        return m.spotify_queue(inputs["query"]) if m else "Spotify not available."

    # ── News
    if name == "news_headlines":
        return news_tool.news_headlines(inputs.get("category", "general"), inputs.get("country", "lk"))
    if name == "news_search":
        return news_tool.news_search(inputs["query"])
    if name == "news_tech":
        return news_tool.news_tech()

    # ── WhatsApp (desktop only)
    if name == "whatsapp_send":
        m = _try_import("whatsapp_tool")
        return m.whatsapp_send(inputs["phone_number"], inputs["message"]) if m else "WhatsApp not available."
    if name == "whatsapp_send_to_contact":
        m = _try_import("whatsapp_tool")
        return m.whatsapp_send_to_contact(inputs["name"], inputs["message"]) if m else "WhatsApp not available."

    return f"Unknown tool: {name}"
