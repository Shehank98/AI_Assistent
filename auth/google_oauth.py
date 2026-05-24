"""
auth/google_oauth.py — Google OAuth2, supports up to 2 accounts.

Account 1 (primary):   GOOGLE_TOKEN_B64     / ~/.jarvis/gmail_token.json
Account 2 (secondary): GOOGLE_TOKEN_B64_2   / ~/.jarvis/gmail_token_2.json

Local setup (run once per account):
    python auth/google_oauth.py           # sets up account 1
    python auth/google_oauth.py --account 2   # sets up account 2

Railway:
    base64 -w0 ~/.jarvis/gmail_token.json    → paste as GOOGLE_TOKEN_B64
    base64 -w0 ~/.jarvis/gmail_token_2.json  → paste as GOOGLE_TOKEN_B64_2
"""

import base64
import json
import os
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/youtube.readonly",
]

_JARVIS_DIR = Path.home() / ".jarvis"


def _token_path(account_num: int) -> Path:
    suffix = "" if account_num == 1 else f"_{account_num}"
    return _JARVIS_DIR / f"gmail_token{suffix}.json"


def _token_env_var(account_num: int) -> str:
    return "GOOGLE_TOKEN_B64" if account_num == 1 else f"GOOGLE_TOKEN_B64_{account_num}"


def get_credentials(account_num: int = 1):
    """
    Return valid Google credentials for the given account number (1 or 2).
    Raises FileNotFoundError if no token is configured for that account.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ImportError(
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    token_path = _token_path(account_num)
    env_var = _token_env_var(account_num)
    creds = None

    # Railway / env-var mode
    token_b64 = os.environ.get(env_var, "")
    if token_b64:
        try:
            token_json = base64.b64decode(token_b64).decode("utf-8")
            token_data = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print(f"[google_oauth] Warning: could not load {env_var}: {e}")

    # Local file mode
    if not creds and token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            if _JARVIS_DIR.exists():
                token_path.write_text(creds.to_json())
        except Exception as e:
            err_str = str(e)
            if "invalid_scope" in err_str:
                print(
                    f"[google_oauth] Account {account_num} token needs re-auth — scopes changed.\n"
                    f"  → Run: python auth/google_oauth.py{'  --account 2' if account_num == 2 else ''}\n"
                    f"  → Then update {env_var} in Railway dashboard."
                )
            else:
                print(f"[google_oauth] Account {account_num} token refresh failed: {e}")
            creds = None

    if not creds:
        # Try interactive OAuth (local only)
        client_secret_paths = [
            Path("client_secret.json"),
            _JARVIS_DIR / "client_secret.json",
        ]
        client_secret_file = next((p for p in client_secret_paths if p.exists()), None)

        if not client_secret_file:
            noun = "primary" if account_num == 1 else f"account {account_num}"
            raise FileNotFoundError(
                f"\nNo Google credentials for {noun} account.\n\n"
                "Setup:\n"
                "  1. Google Cloud Console → create OAuth2 Desktop credentials\n"
                "  2. Download as client_secret.json into AI_Assistent/\n"
                f"  3. Run: python auth/google_oauth.py{'  --account 2' if account_num == 2 else ''}\n"
                f"  4. Set {env_var} in Railway (base64 of the generated token file)"
            )

        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
        creds = flow.run_local_server(port=0)
        _JARVIS_DIR.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        print(f"\n✓ Account {account_num} token saved to {token_path}")
        print(f"\nFor Railway:  base64 -w0 {token_path}  → paste as {env_var}\n")

    return creds


def configured_accounts() -> list[int]:
    """Return list of account numbers that have tokens configured."""
    accounts = []
    for num in [1, 2]:
        env_var = _token_env_var(num)
        if os.environ.get(env_var) or _token_path(num).exists():
            accounts.append(num)
    return accounts or [1]  # always try account 1


if __name__ == "__main__":
    import sys
    account_num = 2 if "--account" in sys.argv and "2" in sys.argv else 1
    print(f"Setting up Google OAuth for account {account_num}...")
    creds = get_credentials(account_num)
    print(f"✓ Account {account_num} authenticated.")
    tp = _token_path(account_num)
    ev = _token_env_var(account_num)
    print(f"\nFor Railway:\n  base64 -w0 {tp}\n  Paste as {ev} in Railway env vars.")
