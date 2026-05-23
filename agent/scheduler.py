"""
agent/scheduler.py — Background jobs using APScheduler.
Replaces the manual asyncio.sleep loop. All jobs run on Asia/Colombo time.
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

    # ── World state refresh (every 5 min) ─────────────────────────────────────
    async def _refresh_world():
        from agent.observer import refresh_world_state
        await refresh_world_state(jarvis.memory)

    # ── Proactive checks (every 15 min) ───────────────────────────────────────
    async def _email_check():
        try:
            from tools.gmail_tool import gmail_important_check
            r = gmail_important_check()
            if r and not r.startswith(("No new", "Error", "Gmail", "Google")):
                jarvis._broadcast_alert(f"📬 {r.splitlines()[0]}")
        except Exception:
            pass

    async def _calendar_check():
        try:
            from tools.calendar_tool import calendar_upcoming
            r = calendar_upcoming(30)
            if r and not r.startswith(("No events", "Error", "Calendar")):
                jarvis._broadcast_alert(f"📅 {r.splitlines()[0]}")
        except Exception:
            pass

    # ── Daily routines ────────────────────────────────────────────────────────
    async def _morning_prep():
        from agent.routines import morning_prep
        await morning_prep(jarvis)

    async def _task_reminder():
        try:
            from tools.memory_tool import list_tasks_due_today
            tasks = list_tasks_due_today()
            if tasks and not tasks.startswith("No tasks"):
                jarvis._broadcast_alert(f"📋 Tasks due today: {tasks.splitlines()[0]}")
        except Exception:
            pass

    async def _evening():
        from agent.routines import evening_review
        await evening_review(jarvis)

    async def _weekly():
        from agent.routines import weekly_review
        await weekly_review(jarvis)

    async def _goals_nudge():
        try:
            from datetime import date
            goals = jarvis.memory.list_goals(status="active")
            overdue = [g for g in goals if g.get("deadline") and g["deadline"] < date.today().isoformat()]
            if overdue:
                names = " | ".join(g["description"][:35] for g in overdue[:3])
                jarvis._broadcast_alert(f"⚠️ Overdue goals: {names}")
        except Exception:
            pass

    jobs = [
        ("world_state",    _refresh_world,    "interval",  {"minutes": 5}),
        ("email_check",    _email_check,      "interval",  {"minutes": 15}),
        ("calendar_check", _calendar_check,   "interval",  {"minutes": 15}),
        ("morning_prep",   _morning_prep,     "cron",      {"hour": 7, "minute": 30}),
        ("task_reminder",  _task_reminder,    "cron",      {"hour": 9, "minute": 0}),
        ("evening_review", _evening,          "cron",      {"hour": 18, "minute": 0}),
        ("weekly_review",  _weekly,           "cron",      {"day_of_week": "sun", "hour": 8}),
        ("goals_nudge",    _goals_nudge,      "cron",      {"hour": 8, "minute": 30}),
    ]

    for job_id, fn, trigger, kwargs in jobs:
        if not sched.get_job(job_id):
            sched.add_job(fn, trigger, id=job_id, replace_existing=True, **kwargs)

    if not sched.running:
        sched.start()

    return sched
