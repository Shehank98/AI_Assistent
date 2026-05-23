"""
agent/routines.py — Autonomous morning, evening, and weekly routines.
Pre-warms data at scheduled times so "good morning" responses are instant.
"""

from datetime import datetime

_morning_cache: dict = {}
_evening_cache: dict = {}


async def morning_prep(jarvis=None):
    """
    7:30am — silently fetch everything needed for the morning briefing.
    When Shehan says 'good morning', response is instant from cache.
    """
    global _morning_cache
    cache: dict = {"built_at": datetime.now().isoformat()}

    for key, fn_path, fn_args in [
        ("weather",  "tools.system_tool.get_weather",        [""]),
        ("emails",   "tools.gmail_tool.gmail_important_check", []),
        ("calendar", "tools.calendar_tool.calendar_today",   []),
        ("news",     "tools.news_tool.news_headlines",        ["general", "lk"]),
    ]:
        try:
            mod_path, fn_name = fn_path.rsplit(".", 1)
            import importlib
            mod = importlib.import_module(mod_path)
            cache[key] = getattr(mod, fn_name)(*fn_args)
        except Exception:
            cache[key] = ""

    # Google Tasks (may not be configured)
    try:
        from tools.google_tasks_tool import tasks_today
        cache["gtasks"] = tasks_today()
    except Exception:
        cache["gtasks"] = ""

    # Jarvis tasks
    try:
        from tools.memory_tool import list_tasks_due_today
        cache["tasks"] = list_tasks_due_today()
    except Exception:
        cache["tasks"] = ""

    _morning_cache = cache

    # Also refresh world state
    if jarvis:
        from agent.observer import refresh_world_state
        await refresh_world_state(jarvis.memory)


async def evening_review(jarvis=None):
    """6:00pm — pre-warm tomorrow's data and nudge Shehan."""
    global _evening_cache
    cache: dict = {"built_at": datetime.now().isoformat()}

    try:
        from tools.calendar_tool import calendar_tomorrow
        cache["tomorrow"] = calendar_tomorrow()
    except Exception:
        cache["tomorrow"] = ""

    try:
        from tools.memory_tool import list_tasks
        cache["pending"] = list_tasks()
    except Exception:
        cache["pending"] = ""

    _evening_cache = cache

    if jarvis:
        jarvis._broadcast_alert(
            "🌆 Evening check — say 'what got done today' for your daily summary"
        )


async def weekly_review(jarvis=None):
    """Sunday 8:00am — prompt for the weekly review."""
    if jarvis:
        jarvis._broadcast_alert(
            "📅 Weekly review — say 'give me a weekly review' to see your week"
        )


def get_morning_cache() -> dict:
    return _morning_cache


def get_evening_cache() -> dict:
    return _evening_cache
