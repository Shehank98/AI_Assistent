"""
tools/gmail_tool.py — Gmail integration via Google API.
Requires: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (+ token via auth/google_oauth.py)
"""

from datetime import datetime, timedelta, timezone


def _get_service():
    from auth.google_oauth import get_credentials
    from googleapiclient.discovery import build
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


def _is_automated(headers: dict) -> bool:
    """Heuristic: is this a newsletter/automated email vs a real person?"""
    from_addr = headers.get("From", "").lower()
    automated_signals = [
        "no-reply", "noreply", "donotreply", "do-not-reply",
        "notifications@", "notification@", "newsletter@",
        "mailer@", "automated@", "support@", "updates@",
        "info@mailchimp", "bounce", "postmaster",
    ]
    if any(s in from_addr for s in automated_signals):
        return True
    if headers.get("List-Unsubscribe"):
        return True
    if headers.get("X-Mailer") or headers.get("List-Id"):
        return True
    return False


def _header_map(msg) -> dict:
    return {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}


def _snippet(msg) -> str:
    return msg.get("snippet", "")[:120]


def _format_date(internal_date: str) -> str:
    try:
        ts = int(internal_date) / 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
        now = datetime.now().astimezone()
        if dt.date() == now.date():
            return dt.strftime("today %I:%M %p")
        elif dt.date() == (now - timedelta(days=1)).date():
            return dt.strftime("yesterday %I:%M %p")
        else:
            return dt.strftime("%b %d")
    except Exception:
        return ""


def gmail_unread(max_results: int = 15) -> str:
    """Return unread emails with sender, subject, snippet, and real-person flag."""
    try:
        svc = _get_service()
        res = svc.users().messages().list(
            userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results
        ).execute()
        messages = res.get("messages", [])
        if not messages:
            return "No unread emails."

        lines = []
        for m in messages:
            msg = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                             metadataHeaders=["From", "Subject", "Date",
                                                              "List-Unsubscribe", "List-Id",
                                                              "X-Mailer"]).execute()
            h = _header_map(msg)
            automated = _is_automated(h)
            tag = "[auto]" if automated else "[person]"
            lines.append(
                f"{tag} From: {h.get('From', '?')} | {_format_date(msg['internalDate'])}\n"
                f"  Subject: {h.get('Subject', '(no subject)')}\n"
                f"  {_snippet(msg)}\n"
                f"  ID: {m['id']}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Gmail error: {e}"


def gmail_search(query: str) -> str:
    """Search inbox by Gmail query string."""
    try:
        svc = _get_service()
        res = svc.users().messages().list(userId="me", q=query, maxResults=10).execute()
        messages = res.get("messages", [])
        if not messages:
            return f"No emails matching: {query}"

        lines = []
        for m in messages:
            msg = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                             metadataHeaders=["From", "Subject"]).execute()
            h = _header_map(msg)
            lines.append(
                f"From: {h.get('From', '?')} | Subject: {h.get('Subject', '(no subject)')} | ID: {m['id']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Gmail search error: {e}"


def gmail_read_full(email_id: str) -> str:
    """Fetch full email body for summarisation."""
    try:
        import base64
        svc = _get_service()
        msg = svc.users().messages().get(userId="me", id=email_id, format="full").execute()
        h = _header_map(msg)

        def _extract_body(payload):
            if payload.get("mimeType") == "text/plain":
                data = payload.get("body", {}).get("data", "")
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            for part in payload.get("parts", []):
                result = _extract_body(part)
                if result:
                    return result
            return ""

        body = _extract_body(msg["payload"])
        return (
            f"From: {h.get('From', '?')}\n"
            f"Subject: {h.get('Subject', '(no subject)')}\n"
            f"Date: {_format_date(msg['internalDate'])}\n\n"
            f"{body[:3000]}"
        )
    except Exception as e:
        return f"Gmail read error: {e}"


def gmail_send(to: str, subject: str, body: str) -> str:
    """Send an email."""
    try:
        import base64
        from email.mime.text import MIMEText
        svc = _get_service()
        msg = MIMEText(body)
        msg["To"] = to
        msg["Subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {to}."
    except Exception as e:
        return f"Gmail send error: {e}"


def gmail_reply(email_id: str, body: str) -> str:
    """Reply to a specific email thread."""
    try:
        import base64
        from email.mime.text import MIMEText
        svc = _get_service()
        orig = svc.users().messages().get(userId="me", id=email_id, format="metadata",
                                          metadataHeaders=["From", "Subject", "Message-Id"]).execute()
        h = _header_map(orig)
        thread_id = orig["threadId"]

        reply = MIMEText(body)
        reply["To"] = h.get("From", "")
        reply["Subject"] = "Re: " + h.get("Subject", "")
        reply["In-Reply-To"] = h.get("Message-Id", "")
        reply["References"] = h.get("Message-Id", "")

        raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw, "threadId": thread_id}).execute()
        return f"Reply sent to {h.get('From', '?')}."
    except Exception as e:
        return f"Gmail reply error: {e}"


def gmail_mark_read(email_id: str) -> str:
    """Mark an email as read."""
    try:
        svc = _get_service()
        svc.users().messages().modify(
            userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        return f"Marked {email_id} as read."
    except Exception as e:
        return f"Gmail mark read error: {e}"


def gmail_important_check() -> str:
    """Return only emails from real people in the last 24h — used by proactive checker."""
    try:
        svc = _get_service()
        after = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
        res = svc.users().messages().list(
            userId="me", q=f"in:inbox after:{after}", maxResults=20
        ).execute()
        messages = res.get("messages", [])
        if not messages:
            return "No new emails from real people in the last 24h."

        lines = []
        for m in messages:
            msg = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                             metadataHeaders=["From", "Subject",
                                                              "List-Unsubscribe", "List-Id",
                                                              "X-Mailer"]).execute()
            h = _header_map(msg)
            if not _is_automated(h):
                lines.append(
                    f"From: {h.get('From', '?')} — {h.get('Subject', '(no subject)')}"
                )

        if not lines:
            return "No new emails from real people in the last 24h."
        return "\n".join(lines)
    except Exception as e:
        return f"Gmail check error: {e}"
