"""
auth/google_oauth.py — Google OAuth2 helper for Gmail + Calendar.

Local first-time setup:
    python auth/google_oauth.py
    → Opens browser, saves token to ~/.jarvis/gmail_token.json

Railway / production:
    base64 ~/.jarvis/gmail_token.json   ← run this locally
    Paste the output as GOOGLE_TOKEN_B64 env var in Railway.
    Token is loaded from the env var at runtime (no file needed).
"""

import base64
import json
import os
from pathlib import Path

TOKEN_PATH = Path.home() / ".jarvis" / "gmail_token.json"

SCOPES = [
    # Gmail
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    # Calendar
    "https://www.googleapis.com/auth/calendar",
    # Tasks
    "https://www.googleapis.com/auth/tasks",
    # Contacts (People API)
    "https://www.googleapis.com/auth/contacts.readonly",
    # Drive (read any file + create/modify files Jarvis creates)
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    # Sheets
    "https://www.googleapis.com/auth/spreadsheets",
    # YouTube read-only (subscription list)
    "https://www.googleapis.com/auth/youtube.readonly",
]


def get_credentials():
    """Return valid Google credentials. Tries env var first, then local file."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ImportError(
            "Google auth libraries not installed.\n"
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    creds = None

    # Railway mode: read token from env var
    token_b64 = os.environ.get("GOOGLE_TOKEN_B64", "")
    if token_b64:
        try:
            token_json = base64.b64decode(token_b64).decode("utf-8")
            token_data = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print(f"[google_oauth] Warning: could not load GOOGLE_TOKEN_B64: {e}")

    # Local mode: read token from file
    if not creds and TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            if TOKEN_PATH.parent.exists():
                TOKEN_PATH.write_text(creds.to_json())
        except Exception as e:
            err_str = str(e)
            if "invalid_scope" in err_str:
                print(
                    "[google_oauth] Token refresh failed: scopes have changed since last auth.\n"
                    "  → Re-run: python auth/google_oauth.py   (locally, not on Railway)\n"
                    "  → Then update GOOGLE_TOKEN_B64 in Railway dashboard."
                )
            else:
                print(f"[google_oauth] Token refresh failed: {e}")
            creds = None

    if not creds:
        # Try OAuth flow for local setup
        client_secret_paths = [
            Path("client_secret.json"),
            Path.home() / ".jarvis" / "client_secret.json",
        ]
        client_secret_file = next((p for p in client_secret_paths if p.exists()), None)

        if not client_secret_file:
            raise FileNotFoundError(
                "\nGoogle credentials not found.\n\n"
                "Setup steps:\n"
                "  1. Go to https://console.cloud.google.com\n"
                "  2. Create a project, enable Gmail API + Google Calendar API\n"
                "  3. Create OAuth2 credentials (Desktop app type)\n"
                "  4. Download as 'client_secret.json' into your jarvis/ folder\n"
                "  5. Run: python auth/google_oauth.py\n\n"
                "For Railway: set GOOGLE_TOKEN_B64 env var (see CLAUDE.md)"
            )

        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
        print(f"\nToken saved to {TOKEN_PATH}")
        print("\nTo deploy on Railway, run:")
        print(f"  base64 {TOKEN_PATH}   # paste as GOOGLE_TOKEN_B64 in Railway env vars\n")

    return creds


if __name__ == "__main__":
    print("Running Google OAuth2 setup...")
    creds = get_credentials()
    print("✓ Authentication successful.")
    print(f"  Token at: {TOKEN_PATH}")
    print(f"\nFor Railway:")
    print(f"  base64 {TOKEN_PATH}")
    print(f"  Paste the output as GOOGLE_TOKEN_B64 in your Railway environment variables.")
