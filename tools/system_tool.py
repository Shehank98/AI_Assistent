"""
tools/system_tool.py — System utilities: weather, time, timers, notes, files, shell.
Desktop-only tools (shell, open_url) are gated behind DESKTOP_MODE=true.
"""

import os
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

NOTES_DIR = Path.home() / "Notes"
DESKTOP_MODE = os.environ.get("DESKTOP_MODE", "false").lower() == "true"
DEFAULT_CITY = os.environ.get("JARVIS_LOCATION", "Colombo")

# Broadcast callback — set by server.py so set_timer can push WebSocket alerts
_broadcast_fn = None


def set_broadcast(fn):
    global _broadcast_fn
    _broadcast_fn = fn


def get_weather(city: str = "") -> str:
    """Current weather. Defaults to JARVIS_LOCATION env var."""
    city = city or DEFAULT_CITY
    try:
        encoded = urllib.parse.quote_plus(city)
        url = f"https://wttr.in/{encoded}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            import json
            data = json.loads(r.read())
        c = data["current_condition"][0]
        desc = c["weatherDesc"][0]["value"]
        temp = c["temp_C"]
        feels = c["FeelsLikeC"]
        humidity = c["humidity"]
        return f"{city}: {desc}, {temp}°C (feels {feels}°C), humidity {humidity}%"
    except Exception as e:
        return f"Weather error: {e}"


def get_datetime() -> str:
    return datetime.now().strftime("%A, %B %d %Y — %I:%M %p")


def set_timer(duration_seconds: int, label: str = "Timer") -> str:
    """Countdown timer. Pushes WebSocket alert when done (server mode) or prints (CLI)."""
    import threading

    def _ring():
        msg = f"⏰ {label} — time's up!"
        print(f"\n[TIMER] {msg}")
        if _broadcast_fn:
            _broadcast_fn(msg)
        else:
            try:
                from voice.tts import speak
                speak(f"{label} done.", voice=True)
            except Exception:
                pass

    t = threading.Timer(duration_seconds, _ring)
    t.daemon = True
    t.start()
    mins, secs = divmod(duration_seconds, 60)
    time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
    return f"Timer set: '{label}' fires in {time_str}."


def create_note(title: str, content: str) -> str:
    """Save a markdown note to ~/Notes/."""
    try:
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        filename = title.lower().replace(" ", "_").replace("/", "-") + ".md"
        path = NOTES_DIR / filename
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        path.write_text(f"# {title}\n_Created: {ts}_\n\n{content}\n", encoding="utf-8")
        return f"Note saved: {path}"
    except Exception as e:
        return f"Error saving note: {e}"


def list_notes() -> str:
    """List all saved notes."""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    notes = sorted(NOTES_DIR.glob("*.md"))
    if not notes:
        return "No notes yet."
    return "\n".join(f"• {n.stem.replace('_', ' ')}" for n in notes)


def read_note(title: str) -> str:
    """Read a note by title (fuzzy match)."""
    slug = title.lower().replace(" ", "_")
    path = NOTES_DIR / (slug + ".md")
    if not path.exists():
        matches = list(NOTES_DIR.glob(f"*{slug}*.md"))
        if matches:
            path = matches[0]
        else:
            return f"Note '{title}' not found. Try list_notes."
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading note: {e}"


def open_url(url: str) -> str:
    """Open a URL in the default browser. Desktop only."""
    if not DESKTOP_MODE:
        return f"open_url is desktop-only. URL: {url}"
    try:
        import webbrowser
        webbrowser.open(url)
        return f"Opened {url}"
    except Exception as e:
        return f"Error: {e}"


def run_shell(command: str, timeout: int = 30) -> str:
    """Run a shell command. Desktop only."""
    if not DESKTOP_MODE:
        return "run_shell is desktop-only (set DESKTOP_MODE=true)."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        parts = []
        if result.stdout.strip():
            parts.append(result.stdout.strip())
        if result.stderr.strip():
            parts.append(f"STDERR: {result.stderr.strip()}")
        parts.append(f"Exit: {result.returncode}")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Shell error: {e}"
