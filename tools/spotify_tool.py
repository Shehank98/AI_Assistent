"""
tools/spotify_tool.py — Spotify playback control via spotipy.
Requires: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET (+ token via auth/spotify_oauth.py)
"""


def _sp():
    from auth.spotify_oauth import get_spotify_client
    return get_spotify_client()


def spotify_play(query: str) -> str:
    """Search and play a song, artist, or playlist."""
    try:
        sp = _sp()
        # Search tracks first, then artists
        results = sp.search(q=query, limit=1, type="track,artist,playlist")
        tracks = results.get("tracks", {}).get("items", [])
        artists = results.get("artists", {}).get("items", [])
        playlists = results.get("playlists", {}).get("items", [])

        if tracks:
            uri = tracks[0]["uri"]
            name = tracks[0]["name"]
            artist = tracks[0]["artists"][0]["name"]
            sp.start_playback(uris=[uri])
            return f"Playing: {name} by {artist}"
        elif playlists:
            uri = playlists[0]["uri"]
            name = playlists[0]["name"]
            sp.start_playback(context_uri=uri)
            return f"Playing playlist: {name}"
        elif artists:
            uri = artists[0]["uri"]
            name = artists[0]["name"]
            sp.start_playback(context_uri=uri)
            return f"Playing top tracks by {name}"
        else:
            return f"Nothing found for: {query}"
    except Exception as e:
        return f"Spotify error: {e}"


def spotify_pause() -> str:
    try:
        _sp().pause_playback()
        return "Paused."
    except Exception as e:
        return f"Spotify pause error: {e}"


def spotify_resume() -> str:
    try:
        _sp().start_playback()
        return "Resumed."
    except Exception as e:
        return f"Spotify resume error: {e}"


def spotify_next() -> str:
    try:
        _sp().next_track()
        return "Skipped to next track."
    except Exception as e:
        return f"Spotify skip error: {e}"


def spotify_current() -> str:
    """What's playing right now."""
    try:
        sp = _sp()
        playback = sp.current_playback()
        if not playback or not playback.get("is_playing"):
            return "Nothing playing right now."
        item = playback.get("item", {})
        name = item.get("name", "?")
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        album = item.get("album", {}).get("name", "")
        progress_ms = playback.get("progress_ms", 0)
        duration_ms = item.get("duration_ms", 1)
        progress = f"{progress_ms // 60000}:{(progress_ms % 60000) // 1000:02d}"
        duration = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
        return f"Playing: {name} by {artists}\nAlbum: {album}\nProgress: {progress} / {duration}"
    except Exception as e:
        return f"Spotify current error: {e}"


def spotify_volume(level: int) -> str:
    """Set volume 0-100."""
    try:
        level = max(0, min(100, int(level)))
        _sp().volume(level)
        return f"Volume set to {level}%."
    except Exception as e:
        return f"Spotify volume error: {e}"


def spotify_queue(query: str) -> str:
    """Add a song to the queue."""
    try:
        sp = _sp()
        results = sp.search(q=query, limit=1, type="track")
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"No track found for: {query}"
        uri = tracks[0]["uri"]
        name = tracks[0]["name"]
        artist = tracks[0]["artists"][0]["name"]
        sp.add_to_queue(uri)
        return f"Queued: {name} by {artist}"
    except Exception as e:
        return f"Spotify queue error: {e}"
