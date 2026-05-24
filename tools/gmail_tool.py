"""
tools/gmail_tool.py — Multi-account Gmail integration.
Account 1 (primary):   GOOGLE_TOKEN_B64
Account 2 (secondary): GOOGLE_TOKEN_B64_2

All functions accept an optional `account` int (1 or 2, default 1).
Combined check functions (gmail_important_check, gmail_all_accounts_summary)
query all configured accounts and merge results.
"""

import os
from datetime import datetime, timedelta, timezone


def _get_service(account: int = 1):
    from auth.google_oauth import get_credentials
    from googleapiclient.discovery import build
    creds = get_credentials(account)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _recover(func: str, exc: Exception, account: int) -> str:
    """Convert an exception to an actionable recovery message for Gemini."""
    msg = str(exc)
    label = f"Account {account}"
    if "invalid_scope" in msg:
        env = "GOOGLE_TOKEN_B64" if account == 1 else f"GOOGLE_TOKEN_B64_{account}"
        return (
            f"[gmail/{label}] Token needs re-auth — OAuth scopes changed. "
            f"RESOLUTION: Run `python auth/google_oauth.py{'  --account 2' if account == 2 else ''}` locally, "
            f"then update {env} in Railway dashboard. Gmail unavailable until then."
        )
    if "No Google credentials" in msg or "FileNotFoundError" in msg:
        return (
            f"[gmail/{label}] Not configured. "
            f"Set {'GOOGLE_TOKEN_B64' if account == 1 else 'GOOGLE_TOKEN_B64_2'} in Railway."
        )
    if "HttpError 401" in msg or "invalid_grant" in msg:
        return f"[gmail/{label}] Token expired/revoked. Re-run Google OAuth setup."
    if "HttpError 403" in msg:
        return f"[gmail/{label}] Permission denied. Check Gmail API is enabled in Google Cloud Console."
    return f"[gmail/{label}] Error: {msg[:200]}"


def _is_automated(headers: dict) -> bool:
    from_addr = headers.get("From", "").lower()
    return any(s in from_addr for s in [
        "no-reply", "noreply", "donotreply", "do-not-reply",
        "notifications@", "notification@", "newsletter@",
        "mailer@", "automated@", "updates@", "info@mailchimp",
        "bounce", "postmaster",
    ]) or bool(
        headers.get("List-Unsubscribe") or
        headers.get("X-Mailer") or
        headers.get("List-Id")
    )


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
        return dt.strftime("%b %d")
    except Exception:
        return ""


# ── Per-account functions ─────────────────────────────────────────────────────

def gmail_unread(max_results: int = 15, account: int = 1) -> str:
    try:
        svc = _get_service(account)
        res = svc.users().messages().list(
            userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results
        ).execute()
        messages = res.get("messages", [])
        if not messages:
            return f"[Account {account}] No unread emails."

        lines = []
        for m in messages:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date", "List-Unsubscribe", "List-Id", "X-Mailer"]
            ).execute()
            h = _header_map(msg)
            tag = "[auto]" if _is_automated(h) else "[person]"
            lines.append(
                f"{tag} From: {h.get('From','?')} | {_format_date(msg['internalDate'])}\n"
                f"  Subject: {h.get('Subject','(no subject)')}\n"
                f"  {_snippet(msg)}\n  ID: {m['id']}"
            )
        return f"[Account {account}]\n\n" + "\n\n".join(lines)
    except Exception as e:
        return _recover("gmail_unread", e, account)


def gmail_search(query: str, account: int = 1) -> str:
    try:
        svc = _get_service(account)
        res = svc.users().messages().list(userId="me", q=query, maxResults=10).execute()
        messages = res.get("messages", [])
        if not messages:
            return f"[Account {account}] No emails matching: {query}"
        lines = []
        for m in messages:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject"]
            ).execute()
            h = _header_map(msg)
            lines.append(
                f"From: {h.get('From','?')} | Subject: {h.get('Subject','(no subject)')} | ID: {m['id']}"
            )
        return f"[Account {account}]\n" + "\n".join(lines)
    except Exception as e:
        return _recover("gmail_search", e, account)


def gmail_read_full(email_id: str, account: int = 1) -> str:
    try:
        import base64
        svc = _get_service(account)
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
            f"From: {h.get('From','?')}\n"
            f"Subject: {h.get('Subject','(no subject)')}\n"
            f"Date: {_format_date(msg['internalDate'])}\n\n"
            f"{body[:3000]}"
        )
    except Exception as e:
        return _recover("gmail_read_full", e, account)


def gmail_send(to: str, subject: str, body: str, account: int = 1) -> str:
    try:
        import base64
        from email.mime.text import MIMEText
        svc = _get_service(account)
        msg = MIMEText(body)
        msg["To"] = to
        msg["Subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {to} from account {account}."
    except Exception as e:
        return _recover("gmail_send", e, account)


def gmail_reply(email_id: str, body: str, account: int = 1) -> str:
    try:
        import base64
        from email.mime.text import MIMEText
        svc = _get_service(account)
        orig = svc.users().messages().get(
            userId="me", id=email_id, format="metadata",
            metadataHeaders=["From", "Subject", "Message-Id"]
        ).execute()
        h = _header_map(orig)
        reply = MIMEText(body)
        reply["To"] = h.get("From", "")
        reply["Subject"] = "Re: " + h.get("Subject", "")
        reply["In-Reply-To"] = h.get("Message-Id", "")
        reply["References"] = h.get("Message-Id", "")
        raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
        svc.users().messages().send(
            userId="me", body={"raw": raw, "threadId": orig["threadId"]}
        ).execute()
        return f"Reply sent to {h.get('From','?')} from account {account}."
    except Exception as e:
        return _recover("gmail_reply", e, account)


def gmail_mark_read(email_id: str, account: int = 1) -> str:
    try:
        svc = _get_service(account)
        svc.users().messages().modify(
            userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        return f"Marked {email_id} as read (account {account})."
    except Exception as e:
        return _recover("gmail_mark_read", e, account)


# ── Cross-account aggregation ─────────────────────────────────────────────────

def gmail_important_check() -> str:
    """
    Check all configured accounts for emails from real people in the last 24h.
    Returns combined results with per-account labels.
    """
    from auth.google_oauth import configured_accounts
    accounts = configured_accounts()
    all_results = []

    for acc in accounts:
        try:
            svc = _get_service(acc)
            after = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
            res = svc.users().messages().list(
                userId="me", q=f"in:inbox after:{after}", maxResults=20
            ).execute()
            messages = res.get("messages", [])
            lines = []
            for m in messages:
                msg = svc.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "List-Unsubscribe", "List-Id", "X-Mailer"]
                ).execute()
                h = _header_map(msg)
                if not _is_automated(h):
                    lines.append(f"  • {h.get('From','?')} — {h.get('Subject','(no subject)')}")
            if lines:
                label = f"Account {acc}" if len(accounts) > 1 else "Inbox"
                all_results.append(f"{label}:\n" + "\n".join(lines))
        except Exception as e:
            all_results.append(_recover("gmail_important_check", e, acc))

    if not all_results:
        return "No new emails from real people in the last 24h."
    return "\n\n".join(all_results)


def gmail_all_accounts_summary() -> str:
    """
    Unread count + latest real-person email summary for all configured accounts.
    Used by morning briefing and proactive notifications.
    """
    from auth.google_oauth import configured_accounts
    accounts = configured_accounts()
    summaries = []

    for acc in accounts:
        try:
            svc = _get_service(acc)
            profile = svc.users().getProfile(userId="me").execute()
            email_addr = profile.get("emailAddress", f"account {acc}")
            unread = profile.get("messagesUnread", "?")

            # Get latest 5 real-person emails
            res = svc.users().messages().list(
                userId="me", q="in:inbox is:unread", maxResults=10
            ).execute()
            messages = res.get("messages", [])
            real_emails = []
            for m in messages:
                msg = svc.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "List-Unsubscribe", "List-Id", "X-Mailer"]
                ).execute()
                h = _header_map(msg)
                if not _is_automated(h):
                    real_emails.append(f"  • {h.get('From','?')} — {h.get('Subject','(no subject)')}")
                if len(real_emails) >= 5:
                    break

            summary = f"📧 {email_addr}: {unread} unread"
            if real_emails:
                summary += "\n" + "\n".join(real_emails)
            summaries.append(summary)
        except Exception as e:
            summaries.append(_recover("gmail_all_accounts_summary", e, acc))

    return "\n\n".join(summaries) if summaries else "No Gmail accounts configured."
