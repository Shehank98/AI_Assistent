"""
tools/google_tasks_tool.py — Google Tasks integration.
Requires 'tasks' scope — re-run auth/google_oauth.py after scope update.
"""

from datetime import datetime, date


def _svc():
    from tools.google_auth import get_service
    return get_service("tasks", "v1")


def _tasklist_id() -> str:
    try:
        result = _svc().tasklists().list(maxResults=1).execute()
        lists = result.get("items", [])
        return lists[0]["id"] if lists else "@default"
    except Exception:
        return "@default"


def tasks_list(max_results: int = 20) -> str:
    try:
        result = _svc().tasks().list(
            tasklist=_tasklist_id(), showCompleted=False, maxResults=max_results
        ).execute()
        items = result.get("items", [])
        if not items:
            return "No pending Google Tasks."
        lines = []
        for t in items:
            due = ""
            if t.get("due"):
                due_dt = datetime.fromisoformat(t["due"].replace("Z", "+00:00"))
                due = f" (due {due_dt.strftime('%b %d')})"
            short_id = t["id"][-6:]
            lines.append(f"[{short_id}] {t['title']}{due}")
        return "\n".join(lines)
    except Exception as e:
        return _scope_error(e, "tasks")


def tasks_create(title: str, due_date: str = "", notes: str = "") -> str:
    try:
        body: dict = {"title": title}
        if due_date:
            body["due"] = f"{due_date}T00:00:00.000Z"
        if notes:
            body["notes"] = notes
        result = _svc().tasks().insert(tasklist=_tasklist_id(), body=body).execute()
        return f"Task created: '{title}' (ID: {result['id'][-6:]})"
    except Exception as e:
        return _scope_error(e, "tasks")


def tasks_complete(task_id: str) -> str:
    try:
        svc = _svc()
        tl = _tasklist_id()
        all_tasks = svc.tasks().list(tasklist=tl, maxResults=100).execute().get("items", [])
        full_id = next((t["id"] for t in all_tasks if t["id"].endswith(task_id) or t["id"] == task_id), None)
        if not full_id:
            return f"Task '{task_id}' not found."
        svc.tasks().patch(tasklist=tl, task=full_id, body={"status": "completed"}).execute()
        return "Task marked complete."
    except Exception as e:
        return _scope_error(e, "tasks")


def tasks_today() -> str:
    try:
        today = date.today().isoformat()
        items = _svc().tasks().list(
            tasklist=_tasklist_id(), showCompleted=False, maxResults=50
        ).execute().get("items", [])
        due = [t["title"] for t in items if t.get("due") and t["due"][:10] <= today]
        if not due:
            return "No Google Tasks due today."
        return "Due today (Google Tasks):\n" + "\n".join(f"- {t}" for t in due)
    except Exception as e:
        return _scope_error(e, "tasks")


def _scope_error(e: Exception, scope: str) -> str:
    msg = str(e).lower()
    if "insufficient" in msg or "permission" in msg or "403" in msg:
        return (f"Google Tasks needs the '{scope}' scope. "
                f"Re-run auth/google_oauth.py to grant it, then re-encode your token.")
    return f"Google Tasks error: {e}"
