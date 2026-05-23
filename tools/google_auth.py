"""
tools/google_auth.py — Shared Google credential loader for all Google tools.
Thin wrapper around auth/google_oauth.py — all new Google tools import from here.
"""


def get_credentials():
    """Return valid Google OAuth2 credentials, auto-refreshing if needed."""
    from auth.google_oauth import get_credentials as _get
    return _get()


def get_service(api_name: str, version: str):
    """Build a Google API service client."""
    from googleapiclient.discovery import build
    return build(api_name, version, credentials=get_credentials(), cache_discovery=False)
