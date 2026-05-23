"""
agent/observer.py — WorldState builder.
Refreshed every 5 minutes by the scheduler. Cached and injected into every
system prompt so Jarvis always has full context about Shehan's world.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class WorldState:
    built_at: Optional[datetime] = None
    current_time: str = ""
    time_of_day: str = ""             # morning / afternoon / evening / night
    upcoming_events: list = field(default_factory=list)
    tasks_due_today: list = field(default_factory=list)
    overdue_tasks: list = field(default_factory=list)
    active_goals: list = field(default_factory=list)
    weather: str = ""
    unread_important: str = ""

    def is_stale(self, max_age_minutes: int = 5) -> bool:
        if self.built_at is None:
            return True
        return (datetime.now() - self.built_at).total_seconds() / 60 > max_age_minutes

    def to_prompt_block(self) -> str:
        """Compact context block prepended to every system prompt."""
        if self.built_at is None:
            return ""

        parts = [f"[Now: {self.current_time}, {self.time_of_day}]"]

        if self.weather:
            parts.append(f"Weather: {self.weather.splitlines()[0][:60]}")

        if self.upcoming_events:
            parts.append("Upcoming: " + " | ".join(self.upcoming_events[:2]))

        today_count = len(self.tasks_due_today)
        overdue_count = len(self.overdue_tasks)
        if today_count or overdue_count:
            task_str = []
            if today_count:
                task_str.append(f"{today_count} due today")
            if overdue_count:
                task_str.append(f"{overdue_count} overdue")
            parts.append("Tasks: " + ", ".join(task_str))

        if self.active_goals:
            goals_str = " | ".join(g["description"][:35] for g in self.active_goals[:2])
            parts.append(f"Goals: {goals_str}")

        if (self.unread_important and
                not self.unread_important.startswith(("No new", "Error", "Gmail", "Google"))):
            parts.append(f"Email: {self.unread_important.splitlines()[0][:70]}")

        return "\n".join(parts)


_state = WorldState()


def get_world_state() -> WorldState:
    return _state


async def refresh_world_state(memory_store=None):
    """Rebuild WorldState from live data. Run by scheduler every 5 min."""
    global _state
    s = WorldState()
    now = datetime.now()
    s.built_at = now
    s.current_time = now.strftime("%A %H:%M")
    hour = now.hour
    s.time_of_day = (
        "morning" if 5 <= hour < 12 else
        "afternoon" if 12 <= hour < 17 else
        "evening" if 17 <= hour < 21 else
        "night"
    )

    try:
        from tools.calendar_tool import calendar_upcoming
        result = calendar_upcoming(90)
        if result and not result.startswith(("No events", "Error", "Calendar")):
            s.upcoming_events = [ln.strip() for ln in result.splitlines() if ln.strip()][:3]
    except Exception:
        pass

    try:
        from tools.system_tool import get_weather
        w = get_weather("")
        s.weather = w.splitlines()[0] if w else ""
    except Exception:
        pass

    if memory_store:
        try:
            from datetime import date
            s.tasks_due_today = [t["task"] for t in memory_store.list_tasks_due_today()]
            today = date.today().isoformat()
            s.overdue_tasks = [
                t["task"] for t in memory_store.list_tasks(done=False)
                if t.get("due_date") and t["due_date"] < today
            ]
            s.active_goals = memory_store.list_goals(status="active")
        except Exception:
            pass

    try:
        from tools.gmail_tool import gmail_important_check
        s.unread_important = gmail_important_check()
    except Exception:
        pass

    _state = s
