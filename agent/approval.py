"""
agent/approval.py — Approval workflow for irreversible Jarvis actions.
Blocks the agent thread until the user approves or denies via PWA modal.
Auto-approves in CLI/voice mode (no WebSocket clients).
"""

import threading
import uuid

_pending: dict[str, dict] = {}  # {approval_id: {"event": Event, "result": bool}}
_broadcast_fn = None


def set_broadcast(fn):
    """Wire up the server's broadcast function. Called once at startup."""
    global _broadcast_fn
    _broadcast_fn = fn


def request_approval(tool_name: str, preview: str, timeout: int = 30) -> bool:
    """
    Block the calling thread until the user approves/denies or the timeout expires.
    Returns True (approved) or False (denied / timeout).
    If no broadcast function is set (CLI mode), auto-approves.
    """
    if _broadcast_fn is None:
        return True  # text/voice mode — no approval UI, just proceed

    approval_id = str(uuid.uuid4())
    event = threading.Event()
    _pending[approval_id] = {"event": event, "result": False}

    _broadcast_fn({
        "type": "approval_request",
        "approval_id": approval_id,
        "action": tool_name,
        "preview": preview,
        "timeout_seconds": timeout,
    })

    got_response = event.wait(timeout=timeout)
    entry = _pending.pop(approval_id, {})
    # Timeout with no response → deny by default (safe)
    return entry.get("result", False) if got_response else False


def respond_approval(approval_id: str, granted: bool):
    """Called from server.py when the user clicks Approve/Deny in the PWA."""
    entry = _pending.get(approval_id)
    if entry:
        entry["result"] = granted
        entry["event"].set()
