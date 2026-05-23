"""
tools/youtube_tool.py — YouTube transcript fetcher.
Uses youtube-transcript-api (no API key needed).
"""

import re


def youtube_transcript(url: str, max_chars: int = 8000) -> str:
    """
    Fetch the transcript of a YouTube video.
    Works with youtu.be, youtube.com/watch, /shorts URLs.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
    except ImportError:
        return "youtube-transcript-api not installed. Run: pip install youtube-transcript-api"

    video_id = _extract_id(url)
    if not video_id:
        return f"Couldn't extract video ID from: {url}"

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Prefer manual English, then auto-generated, then anything
        try:
            t = transcript_list.find_manually_created_transcript(["en", "en-US", "en-GB"])
        except NoTranscriptFound:
            try:
                t = transcript_list.find_generated_transcript(["en", "si", "ta"])
            except NoTranscriptFound:
                t = next(iter(transcript_list))

        data = t.fetch()
        text = " ".join(entry["text"] for entry in data)

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[Truncated — full transcript is {len(text):,} chars]"

        return f"[YouTube Transcript — {video_id}]\n\n{text}"

    except Exception as e:
        return f"Transcript error: {e}"


def youtube_summarise(url: str) -> str:
    """
    Fetch transcript ready for Jarvis to summarise.
    Jarvis will read the transcript and provide key points.
    """
    transcript = youtube_transcript(url)
    if transcript.startswith("[YouTube Transcript"):
        return transcript + "\n\n[Please summarise the above transcript in 3-5 key points, conversationally]"
    return transcript


def _extract_id(url: str) -> str | None:
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    # Bare video ID
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url.strip()):
        return url.strip()
    return None
