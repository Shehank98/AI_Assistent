"""
agent/scheduler.py — Background jobs using APScheduler.
Replaces the manual asyncio.sleep loop that was in jarvis.py.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Colombo")
    return _scheduler


def setup_scheduler(jarvis) -> AsyncIOScheduler:
    """Register all background jobs and start the scheduler. Called once at startup."""
    sched = get_scheduler()

    async def _email_check():
        try:
            from tools.gmail_tool import gmail_important_check
            result = gmail_important_check()
            if result and not result.startswith(("No new", "Error", "Gmail", "Google")):
                jarvis._broadcast_alert(f"📬 {result.splitlines()[0]}")
        except Exception:
            pass

    async def _calendar_check():
        try:
            from tools.calendar_tool import calendar_upcoming
            result = calendar_upcoming(30)
            if result and not result.startswith(("No events", "Error", "Calendar", "Google")):
                jarvis._broadcast_alert(f"📅 {result.splitlines()[0]}")
        except Exception:
            pass

    async def _task_reminder():
        try:
            from tools.memory_tool import list_tasks_due_today
            tasks = list_tasks_due_today()
            if tasks and not tasks.startswith("No tasks"):
                first = tasks.splitlines()[0]
                jarvis._broadcast_alert(f"📋 Tasks due today: {first}")
        except Exception:
            pass

    async def _active_goals_nudge():
        """Once a day: surface any overdue goals."""
        try:
            from datetime import date
            goals = jarvis.memory.list_goals(status="active")
            overdue = [
                g for g in goals
                if g["deadline"] and g["deadline"] < date.today().isoformat()
            ]
            if overdue:
                names = ", ".join(g["description"][:40] for g in overdue[:3])
                jarvis._broadcast_alert(f"⚠️ Overdue goals: {names}")
        except Exception:
            pass

    if not sched.get_job("email_check"):
        sched.add_job(_email_check, "interval", minutes=15, id="email_check")
    if not sched.get_job("calendar_check"):
        sched.add_job(_calendar_check, "interval", minutes=15, id="calendar_check")
    if not sched.get_job("task_reminder"):
        sched.add_job(_task_reminder, "cron", hour=9, minute=0, id="task_reminder")
    if not sched.get_job("goals_nudge"):
        sched.add_job(_active_goals_nudge, "cron", hour=8, minute=30, id="goals_nudge")

    if not sched.running:
        sched.start()

    return sched
