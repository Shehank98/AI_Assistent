"""
tools/memory_tool.py — Memory and task management tools.
Operates on the MemoryStore injected via set_memory_store().
"""

_store = None


def set_store(store):
    global _store
    _store = store


def _require_store():
    if _store is None:
        raise RuntimeError("Memory store not initialised.")
    return _store


def remember(key: str, value: str) -> str:
    _require_store().save_fact(key, value)
    return f"Remembered: {key} = {value}"


def recall(key: str) -> str:
    store = _require_store()
    value = store.get_fact(key)
    return f"{key}: {value}" if value else f"Nothing stored for '{key}'."


def recall_all() -> str:
    facts = _require_store().get_all_facts()
    if not facts:
        return "Nothing stored yet."
    return "\n".join(f"{k}: {v}" for k, v in facts.items())


def forget(key: str) -> str:
    _require_store().delete_fact(key)
    return f"Forgot: {key}"


def add_task(task: str, due_date: str = "") -> str:
    """Save a task. due_date format: YYYY-MM-DD (optional)."""
    store = _require_store()
    task_id = store.add_task(task, due_date or None)
    due = f" (due {due_date})" if due_date else ""
    return f"Task added{due}: [{task_id}] {task}"


def list_tasks() -> str:
    tasks = _require_store().list_tasks()
    if not tasks:
        return "No pending tasks."
    return "\n".join(f"[{t['id']}] {t['task']}" + (f" (due {t['due_date']})" if t.get("due_date") else "")
                     for t in tasks)


def complete_task(task_id: int) -> str:
    _require_store().complete_task(int(task_id))
    return f"Task {task_id} marked done."


def list_tasks_due_today() -> str:
    tasks = _require_store().list_tasks_due_today()
    if not tasks:
        return "No tasks due today."
    return "\n".join(f"[{t['id']}] {t['task']}" for t in tasks)
