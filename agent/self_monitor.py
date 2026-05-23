"""
agent/self_monitor.py — Jarvis self-awareness and health.
Tracks uptime, API calls, tool health, recent actions.
Provides honest introspective answers when Shehan asks "how are you".
"""

import os
import time
from datetime import datetime

_start_time = time.time()
_action_log: list[dict] = []
_error_log: list[dict] = []
_api_calls_today: int = 0
_api_calls_date: str = ""


def record_action(tool_name: str, success: bool = True, note: str = ""):
    global _action_log
    _action_log.append({
        "tool": tool_name, "success": success,
        "note": note, "at": datetime.now().strftime("%H:%M"),
    })
    _action_log = _action_log[-200:]


def record_error(context: str, error: str):
    global _error_log
    _error_log.append({"context": context, "error": str(error)[:120],
                        "at": datetime.now().isoformat()})
    _error_log = _error_log[-30:]


def tick_api_call():
    global _api_calls_today, _api_calls_date
    today = datetime.now().strftime("%Y-%m-%d")
    if today != _api_calls_date:
        _api_calls_today = 0
        _api_calls_date = today
    _api_calls_today += 1


def get_uptime() -> str:
    s = int(time.time() - _start_time)
    h, m = s // 3600, (s % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m"


def get_recent_actions(n: int = 5) -> list[dict]:
    return _action_log[-n:]


def get_last_error() -> str:
    if not _error_log:
        return "none"
    e = _error_log[-1]
    return f"{e['context']}: {e['error'][:80]} ({e['at'][:16]})"


def health_check(memory_store=None) -> dict:
    facts, goals, tasks = 0, 0, 0
    if memory_store:
        try:
            facts = len(memory_store.get_all_facts())
            goals = len(memory_store.list_goals("active"))
            tasks = len(memory_store.list_tasks(done=False))
        except Exception:
            pass

    def _google_ok():
        return bool(
            os.environ.get("GOOGLE_TOKEN_B64") or
            (__import__("pathlib").Path.home() / ".jarvis" / "gmail_token.json").exists()
        )

    return {
        "uptime": get_uptime(),
        "api_calls_today": _api_calls_today,
        "facts_learned": facts,
        "goals_active": goals,
        "tasks_pending": tasks,
        "last_error": get_last_error(),
        "actions_logged": len(_action_log),
        "tools": {
            "memory": True,
            "web": True,
            "gmail": _google_ok(),
            "calendar": _google_ok(),
            "spotify": bool(os.environ.get("SPOTIFY_CLIENT_ID")),
            "github": bool(os.environ.get("GITHUB_TOKEN")),
        },
    }


def introspect(memory_store=None) -> str:
    h = health_check(memory_store)
    broken = [k for k, v in h["tools"].items() if not v]
    tool_str = "all tools working" if not broken else f"{', '.join(broken)} offline"
    recent = _action_log[-1] if _action_log else None
    last_str = f"Last: {recent['tool']} ({'ok' if recent['success'] else 'failed'})." if recent else ""
    return (
        f"Up {h['uptime']}. Learned {h['facts_learned']} things about you. "
        f"{h['goals_active']} active goals, {h['tasks_pending']} pending tasks. "
        f"{h['api_calls_today']} API calls today. {tool_str}. {last_str}"
    ).strip()
