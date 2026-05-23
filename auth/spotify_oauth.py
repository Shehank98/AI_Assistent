"""
auth/spotify_oauth.py — Spotify OAuth helper via spotipy.

Local first-time setup:
    python auth/spotify_oauth.py
    → Opens browser, saves token to ~/.jarvis/spotify_token.json

Railway / production:
    base64 ~/.jarvis/spotify_token.json   ← run this locally
    Paste as SPOTIFY_TOKEN_B64 env var in Railway.
"""

import base64
import json
import os
from pathlib import Path

TOKEN_PATH = Path.home() / ".jarvis" / "spotify_token.json"

SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "user-read-recently-played",
])


def get_spotify_client():
    """Return an authenticated spotipy.Spotify client."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        raise ImportError("spotipy not installed. Run: pip install spotipy")

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

    if not client_id or not client_secret:
        raise ValueError(
            "\nSpotify credentials not configured.\n\n"
            "Setup steps:\n"
            "  1. Go to https://developer.spotify.com/dashboard\n"
            "  2. Create an app, grab Client ID and Client Secret\n"
            "  3. Add redirect URI: http://localhost:8888/callback (for local)\n"
            "     Or your Railway URL: https://your-app.railway.app/auth/spotify\n"
            "  4. Set env vars: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET\n"
            "  5. Run: python auth/spotify_oauth.py\n"
        )

    # Railway mode: load cached token from env var
    token_b64 = os.environ.get("SPOTIFY_TOKEN_B64", "")
    cache_path = str(TOKEN_PATH)

    if token_b64:
        try:
            token_json = base64.b64decode(token_b64).decode("utf-8")
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(token_json)
        except Exception as e:
            print(f"[spotify_oauth] Warning: could not load SPOTIFY_TOKEN_B64: {e}")

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPES,
        cache_path=cache_path,
        open_browser=False,
    )

    return spotipy.Spotify(auth_manager=auth_manager)


if __name__ == "__main__":
    import webbrowser

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        print("Install spotipy first: pip install spotipy")
        raise SystemExit(1)

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET first.")
        raise SystemExit(1)

    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://localhost:8888/callback",
        scope=SCOPES,
        cache_path=str(TOKEN_PATH),
    )

    auth_url = auth.get_authorize_url()
    print(f"\nOpening browser for Spotify auth...")
    webbrowser.open(auth_url)
    response_url = input("Paste the redirect URL here: ").strip()
    code = auth.parse_response_code(response_url)
    auth.get_access_token(code)

    print(f"\n✓ Spotify token saved to {TOKEN_PATH}")
    print(f"\nFor Railway:")
    print(f"  base64 {TOKEN_PATH}")
    print(f"  Paste output as SPOTIFY_TOKEN_B64 in Railway env vars.")
