"""
tools/calendar_tool.py — Google Calendar integration.
Shares OAuth credentials with gmail_tool (same token file).
"""

from datetime import datetime, timedelta, timezone


def _get_service():
    from auth.google_oauth import get_credentials
    from googleapiclient.discovery import build
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds)


def _fmt_event(event: dict) -> str:
    summary = event.get("summary", "(no title)")
    start = event.get("start", {})
    dt_str = start.get("dateTime", start.get("date", ""))
    location = event.get("location", "")
    desc = event.get("description", "")

    # Try to extract meeting link
    meeting_link = ""
    for field in [desc, location]:
        for prefix in ("https://meet.google.com/", "https://zoom.us/", "https://teams.microsoft.com/"):
            if prefix in field:
                start_idx = field.index(prefix)
                end_idx = field.find(" ", start_idx)
                meeting_link = field[start_idx:end_idx if end_idx > 0 else start_idx + 80]
                break

    time_str = ""
    if "T" in dt_str:
        try:
            dt = datetime.fromisoformat(dt_str)
            time_str = dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            time_str = dt_str
    else:
        time_str = "all day"

    parts = [f"{time_str} — {summary}"]
    if location and not meeting_link:
        parts.append(f"  📍 {location}")
    if meeting_link:
        parts.append(f"  🔗 {meeting_link}")

    return "\n".join(parts)


def _events_between(start_dt: datetime, end_dt: datetime) -> list[dict]:
    svc = _get_service()
    res = svc.events().list(
        calendarId="primary",
        timeMin=start_dt.isoformat(),
        timeMax=end_dt.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return res.get("items", [])


def calendar_today() -> str:
    """All events today."""
    try:
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        events = _events_between(start, end)
        if not events:
            return "Nothing on the calendar today."
        return "Today:\n" + "\n\n".join(_fmt_event(e) for e in events)
    except Exception as e:
        return f"Calendar error: {e}"


def calendar_tomorrow() -> str:
    """Tomorrow's events."""
    try:
        now = datetime.now().astimezone()
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        events = _events_between(start, end)
        if not events:
            return "Nothing on the calendar tomorrow."
        return "Tomorrow:\n" + "\n\n".join(_fmt_event(e) for e in events)
    except Exception as e:
        return f"Calendar error: {e}"


def calendar_week() -> str:
    """Next 7 days grouped by day."""
    try:
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        events = _events_between(start, end)
        if not events:
            return "Nothing in the next 7 days."

        by_day: dict[str, list] = {}
        for event in events:
            dt_str = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
            if "T" in dt_str:
                day = datetime.fromisoformat(dt_str).strftime("%A, %b %d")
            else:
                day = datetime.strptime(dt_str, "%Y-%m-%d").strftime("%A, %b %d")
            by_day.setdefault(day, []).append(_fmt_event(event))

        sections = []
        for day, evts in by_day.items():
            sections.append(f"**{day}**\n" + "\n\n".join(evts))
        return "\n\n".join(sections)
    except Exception as e:
        return f"Calendar error: {e}"


def calendar_upcoming(minutes: int = 30) -> str:
    """Events starting within N minutes — used by proactive checker."""
    try:
        now = datetime.now().astimezone()
        end = now + timedelta(minutes=minutes)
        events = _events_between(now, end)
        if not events:
            return f"No events in the next {minutes} minutes."
        return "\n\n".join(_fmt_event(e) for e in events)
    except Exception as e:
        return f"Calendar error: {e}"


def calendar_create(title: str, date: str, time: str, duration_minutes: int = 60,
                    description: str = "") -> str:
    """Create a calendar event. date: YYYY-MM-DD, time: HH:MM (24h)."""
    try:
        svc = _get_service()
        start_str = f"{date}T{time}:00"
        start_dt = datetime.fromisoformat(start_str).astimezone()
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": str(start_dt.tzinfo)},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": str(end_dt.tzinfo)},
        }
        created = svc.events().insert(calendarId="primary", body=event).execute()
        return f"Event created: '{title}' on {date} at {time} (ID: {created.get('id', '?')})"
    except Exception as e:
        return f"Calendar create error: {e}"


def calendar_delete(event_id: str) -> str:
    """Delete a calendar event by ID."""
    try:
        svc = _get_service()
        svc.events().delete(calendarId="primary", eventId=event_id).execute()
        return f"Event {event_id} deleted."
    except Exception as e:
        return f"Calendar delete error: {e}"
