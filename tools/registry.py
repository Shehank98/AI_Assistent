"""
tools/registry.py — Central tool registry for Jarvis.
All tools exposed to Gemini are defined and dispatched here.
Desktop-only tools are excluded when DESKTOP_MODE != "true".
"""

import os

DESKTOP_MODE = os.environ.get("DESKTOP_MODE", "false").lower() == "true"

_memory_store = None


def set_memory_store(store):
    global _memory_store
    _memory_store = store
    from tools.memory_tool import set_store
    set_store(store)


_TOOLS_BASE = [
    # ── Web / Search ──────────────────────────────────────────────────────────
    {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo.",
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
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "youtube_search",
        "description": "Search YouTube and return top 3 results.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "wikipedia",
        "description": "Get a Wikipedia summary for a topic.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },

    # ── System / Utilities ────────────────────────────────────────────────────
    {
        "name": "get_weather",
        "description": "Get current weather for a city. Defaults to JARVIS_LOCATION.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
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
        "description": "Set a countdown timer that alerts when done.",
        "input_schema": {
            "type": "object",
            "properties": {
                "duration_seconds": {"type": "integer"},
                "label": {"type": "string"},
            },
            "required": ["duration_seconds"],
        },
    },
    {
        "name": "create_note",
        "description": "Save a note to ~/Notes/ as markdown.",
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
        "description": "Read contents of a file from disk.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
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
            "properties": {"path": {"type": "string"}},
            "required": [],
        },
    },

    # ── Memory ────────────────────────────────────────────────────────────────
    {
        "name": "remember",
        "description": "Save a fact about Shehan for future sessions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
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
        "description": "Add a task with optional due date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "due_date": {"type": "string", "description": "YYYY-MM-DD"},
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
        "description": "Mark a task as done by ID.",
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
    {
        "name": "learn_preference",
        "description": "Silently save a preference or habit Shehan mentioned in passing. Call without announcing. Examples: 'schedule' + 'hates meetings before 10am', 'communication' + 'prefers bullet points'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category: schedule|food|music|communication|health|work|social|other"},
                "preference": {"type": "string", "description": "The preference or habit in plain language"},
            },
            "required": ["category", "preference"],
        },
    },
    {
        "name": "get_profile",
        "description": "Return Shehan's full profile: all learned facts, preferences, and routines.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "update_routine",
        "description": "Save or update one of Shehan's routines (morning, gym, work-start, bedtime, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "routine_name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["routine_name", "description"],
        },
    },
    {
        "name": "log_mood",
        "description": "Silently log Shehan's mood when emotional context is detectable. Never mention this to him.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mood": {"type": "string", "description": "e.g. stressed, happy, tired, focused"},
                "context": {"type": "string", "description": "Brief context (optional)"},
            },
            "required": ["mood"],
        },
    },

    # ── Goals ─────────────────────────────────────────────────────────────────
    {
        "name": "create_goal",
        "description": "Create a persistent goal tracked across sessions. Use for multi-step objectives, 'remind me until X happens', or anything Shehan wants Jarvis to keep track of long-term.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "The goal to achieve"},
                "deadline": {"type": "string", "description": "Optional deadline in YYYY-MM-DD format"},
            },
            "required": ["description"],
        },
    },
    {
        "name": "list_goals",
        "description": "List goals by status. Use to check what's being tracked.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "active | completed | all (default: active)"},
            },
            "required": [],
        },
    },
    {
        "name": "complete_goal",
        "description": "Mark a goal as achieved with an optional result summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer", "description": "Goal ID from list_goals"},
                "result": {"type": "string", "description": "What was accomplished (optional)"},
            },
            "required": ["goal_id"],
        },
    },
    {
        "name": "cancel_goal",
        "description": "Cancel an active goal that is no longer needed.",
        "input_schema": {
            "type": "object",
            "properties": {"goal_id": {"type": "integer"}},
            "required": ["goal_id"],
        },
    },

    # ── Research agent ────────────────────────────────────────────────────────
    {
        "name": "research_agent",
        "description": "Spawn a focused research sub-agent that searches multiple sources and returns a synthesised brief. Use for deep research that needs more than one or two searches — market analysis, technical deep-dives, news aggregation, background on a person/company/topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "What to research"},
                "depth": {"type": "string", "description": "shallow (3 searches) | medium (6) | deep (12). Default: medium"},
            },
            "required": ["topic"],
        },
    },

    # ── Google Tasks ──────────────────────────────────────────────────────────
    {
        "name": "tasks_list",
        "description": "List all pending Google Tasks (syncs with phone).",
        "input_schema": {"type": "object", "properties": {"max_results": {"type": "integer"}}, "required": []},
    },
    {
        "name": "tasks_create",
        "description": "Create a Google Task (appears on phone). Use instead of add_task when the user wants it in Google Tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "due_date": {"type": "string", "description": "YYYY-MM-DD"},
                "notes": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "tasks_complete",
        "description": "Mark a Google Task as completed by its short ID.",
        "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]},
    },
    {
        "name": "tasks_today",
        "description": "List Google Tasks due today.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },

    # ── Google Contacts ───────────────────────────────────────────────────────
    {
        "name": "contacts_search",
        "description": "Search Google Contacts by name. Returns name + email + phone. Use before sending email to look up someone's address.",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    },
    {
        "name": "contacts_get_email",
        "description": "Get the email address for a contact by name. Use when Shehan says 'email [name]' without specifying the address.",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    },
    {
        "name": "contacts_list_frequent",
        "description": "List recently modified Google Contacts.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },

    # ── Google Drive ──────────────────────────────────────────────────────────
    {
        "name": "drive_search",
        "description": "Search Google Drive files by name or content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "description": "Default 8"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "drive_read",
        "description": "Read the content of a Google Doc or text file by Drive file ID.",
        "input_schema": {"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]},
    },
    {
        "name": "drive_list_recent",
        "description": "List Google Drive files modified in the last N days.",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer"}}, "required": []},
    },
    {
        "name": "drive_create_doc",
        "description": "Create a new Google Doc with content. Use for saving research briefs, weekly reviews, etc.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "content": {"type": "string"}},
            "required": ["title", "content"],
        },
    },

    # ── Google Sheets ─────────────────────────────────────────────────────────
    {
        "name": "sheets_read",
        "description": "Read data from a Google Sheets spreadsheet. Requires spreadsheet_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string"},
                "range_": {"type": "string", "description": "e.g. Sheet1!A1:E20"},
            },
            "required": ["spreadsheet_id"],
        },
    },
    {
        "name": "sheets_append",
        "description": "Append a row of data to a Google Sheets spreadsheet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string"},
                "values": {"type": "array", "items": {"type": "string"}, "description": "Row values"},
                "sheet_name": {"type": "string", "description": "Default: Sheet1"},
            },
            "required": ["spreadsheet_id", "values"],
        },
    },
    {
        "name": "sheets_create",
        "description": "Create a new Google Spreadsheet with optional column headers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "headers": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title"],
        },
    },

    # ── YouTube ───────────────────────────────────────────────────────────────
    {
        "name": "youtube_transcript",
        "description": "Fetch the full transcript of a YouTube video by URL. Use to summarise videos, extract key info, or answer questions about video content.",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
    {
        "name": "youtube_summarise",
        "description": "Fetch YouTube transcript and prepare it for summarisation. Returns transcript with a summarise prompt.",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },

    # ── Code execution ────────────────────────────────────────────────────────
    {
        "name": "run_python",
        "description": "Execute Python code in a sandboxed subprocess. Returns stdout/stderr. Use for calculations, data processing, quick scripts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "timeout": {"type": "integer", "description": "Seconds, default 15"},
            },
            "required": ["code"],
        },
    },

    # ── GitHub ────────────────────────────────────────────────────────────────
    {
        "name": "github_search",
        "description": "Search GitHub repositories, code, or issues. Requires GITHUB_TOKEN.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "type_": {"type": "string", "description": "repositories | code | issues"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "github_create_issue",
        "description": "Create a GitHub issue. Requires GITHUB_TOKEN.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo"},
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["repo", "title"],
        },
    },
    {
        "name": "github_my_repos",
        "description": "List your GitHub repositories sorted by recent activity.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },

    # ── Self-awareness ────────────────────────────────────────────────────────
    {
        "name": "jarvis_status",
        "description": "Return Jarvis's own health: uptime, tools, facts learned, active goals. Use when asked 'how are you', 'are you working', 'what do you know about me'.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },

    # ── Gmail ─────────────────────────────────────────────────────────────────
    {
        "name": "gmail_unread",
        "description": "Get unread emails. Flags [person] vs [auto]. account=1 primary, account=2 secondary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer"},
                "account": {"type": "integer", "description": "1=primary (default), 2=secondary"},
            },
            "required": [],
        },
    },
    {
        "name": "gmail_search",
        "description": "Search Gmail by query string. account=1 or 2 to target a specific inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "account": {"type": "integer", "description": "1=primary (default), 2=secondary"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "gmail_read_full",
        "description": "Read the full body of an email by ID. Note: email content is sent to Gemini API.",
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
                "to": {"type": "string"},
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
        "description": "Check all configured Gmail accounts for emails from real people in the last 24h.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "gmail_all_accounts_summary",
        "description": "Get unread count and important email summary for all configured Gmail accounts. Use for morning briefing and proactive notifications.",
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
        "description": "Get events for the next 7 days.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calendar_upcoming",
        "description": "Get events starting within N minutes (default 30).",
        "input_schema": {
            "type": "object",
            "properties": {"minutes": {"type": "integer"}},
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
                "duration_minutes": {"type": "integer"},
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
            "properties": {"query": {"type": "string"}},
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
        "description": "Skip to next track on Spotify.",
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
            "properties": {"level": {"type": "integer"}},
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
        "description": "Get top headlines. category: general/tech/world/business.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "country": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "news_search",
        "description": "Search news by topic.",
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

    # ── RAG / Document Knowledge Base ─────────────────────────────────────────
    {
        "name": "query_docs",
        "description": (
            "Semantic search across all uploaded files — Excel sheets, PDFs, CSVs, text docs. "
            "Use whenever the user asks about data or content from a file they've uploaded. "
            "Always cite the source file, sheet, and row range in your answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "k": {"type": "integer", "description": "Number of results (default 5)"},
                "source": {"type": "string", "description": "Optional: filter by filename"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_documents",
        "description": "List all files that have been uploaded and indexed in the knowledge base.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "delete_document",
        "description": "Remove a file and all its content from the knowledge base by filename.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Exact filename to delete"},
            },
            "required": ["source"],
        },
    },
]

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
                "timeout": {"type": "integer"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "whatsapp_send",
        "description": "Send a WhatsApp message. Desktop only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string"},
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
                "name": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["name", "message"],
        },
    },
]

TOOLS = _TOOLS_BASE + (_TOOLS_DESKTOP if DESKTOP_MODE else [])


def handle_tool_call(name: str, inputs: dict) -> str:
    from tools import memory_tool, web_tool, system_tool, news_tool

    def _try_import(module_name):
        try:
            import importlib
            return importlib.import_module(f"tools.{module_name}")
        except Exception:
            return None

    PRIVACY_MODE = os.environ.get("PRIVACY_MODE", "false").lower() == "true"

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
    if name == "learn_preference":
        return memory_tool.learn_preference(inputs["category"], inputs["preference"])
    if name == "get_profile":
        return memory_tool.get_profile()
    if name == "update_routine":
        return memory_tool.update_routine(inputs["routine_name"], inputs["description"])
    if name == "log_mood":
        return memory_tool.log_mood(inputs["mood"], inputs.get("context", ""))

    # ── Goals
    if name == "create_goal":
        return memory_tool.create_goal(inputs["description"], inputs.get("deadline", ""))
    if name == "list_goals":
        return memory_tool.list_goals(inputs.get("status", "active"))
    if name == "complete_goal":
        return memory_tool.complete_goal(inputs["goal_id"], inputs.get("result", ""))
    if name == "cancel_goal":
        return memory_tool.cancel_goal(inputs["goal_id"])

    # research_agent is handled directly in jarvis.py's agentic loop

    # ── Google Tasks
    if name == "tasks_list":
        from tools.google_tasks_tool import tasks_list
        return tasks_list(inputs.get("max_results", 20))
    if name == "tasks_create":
        from tools.google_tasks_tool import tasks_create
        return tasks_create(inputs["title"], inputs.get("due_date", ""), inputs.get("notes", ""))
    if name == "tasks_complete":
        from tools.google_tasks_tool import tasks_complete
        return tasks_complete(inputs["task_id"])
    if name == "tasks_today":
        from tools.google_tasks_tool import tasks_today
        return tasks_today()

    # ── Google Contacts
    if name == "contacts_search":
        from tools.google_contacts_tool import contacts_search
        return contacts_search(inputs["name"])
    if name == "contacts_get_email":
        from tools.google_contacts_tool import contacts_get_email
        return contacts_get_email(inputs["name"])
    if name == "contacts_list_frequent":
        from tools.google_contacts_tool import contacts_list_frequent
        return contacts_list_frequent()

    # ── Google Drive
    if name == "drive_search":
        from tools.google_drive_tool import drive_search
        return drive_search(inputs["query"], inputs.get("max_results", 8))
    if name == "drive_read":
        from tools.google_drive_tool import drive_read
        return drive_read(inputs["file_id"])
    if name == "drive_list_recent":
        from tools.google_drive_tool import drive_list_recent
        return drive_list_recent(inputs.get("days", 7))
    if name == "drive_create_doc":
        from tools.google_drive_tool import drive_create_doc
        return drive_create_doc(inputs["title"], inputs["content"])

    # ── Google Sheets
    if name == "sheets_read":
        from tools.google_sheets_tool import sheets_read
        return sheets_read(inputs["spreadsheet_id"], inputs.get("range_", "Sheet1!A1:Z100"))
    if name == "sheets_append":
        from tools.google_sheets_tool import sheets_append
        return sheets_append(inputs["spreadsheet_id"], inputs["values"], inputs.get("sheet_name", "Sheet1"))
    if name == "sheets_create":
        from tools.google_sheets_tool import sheets_create
        return sheets_create(inputs["title"], inputs.get("headers"))

    # ── YouTube
    if name == "youtube_transcript":
        from tools.youtube_tool import youtube_transcript
        return youtube_transcript(inputs["url"])
    if name == "youtube_summarise":
        from tools.youtube_tool import youtube_summarise
        return youtube_summarise(inputs["url"])

    # ── Code
    if name == "run_python":
        from tools.code_tool import run_python
        return run_python(inputs["code"], inputs.get("timeout", 15))

    # ── GitHub
    if name == "github_search":
        from tools.github_tool import github_search
        return github_search(inputs["query"], inputs.get("type_", "repositories"))
    if name == "github_create_issue":
        from tools.github_tool import github_create_issue
        return github_create_issue(inputs["repo"], inputs["title"], inputs.get("body", ""))
    if name == "github_my_repos":
        from tools.github_tool import github_my_repos
        return github_my_repos()

    # ── Self-awareness
    if name == "jarvis_status":
        from agent.self_monitor import introspect
        from tools.memory_tool import _store
        return introspect(_store)

    # ── Gmail
    if name == "gmail_unread":
        m = _try_import("gmail_tool")
        return m.gmail_unread(inputs.get("max_results", 15), inputs.get("account", 1)) if m else "Gmail not available."
    if name == "gmail_search":
        m = _try_import("gmail_tool")
        return m.gmail_search(inputs["query"], inputs.get("account", 1)) if m else "Gmail not available."
    if name == "gmail_read_full":
        if PRIVACY_MODE:
            return "gmail_read_full is disabled in PRIVACY_MODE. Email content stays local."
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
    if name == "gmail_all_accounts_summary":
        m = _try_import("gmail_tool")
        return m.gmail_all_accounts_summary() if m else "Gmail not available."

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

    # ── RAG / Document Knowledge Base
    if name == "query_docs":
        from tools.rag_tool import query_docs
        return query_docs(inputs["query"], inputs.get("k", 5), inputs.get("source", ""))
    if name == "list_documents":
        from tools.rag_tool import list_documents
        return list_documents()
    if name == "delete_document":
        from tools.rag_tool import delete_document
        return delete_document(inputs["source"])

    return f"Unknown tool: {name}"
