"""
voice/tts.py — Text-to-speech

Priority order:
  1. ElevenLabs streaming (cloud, most realistic) — set ELEVENLABS_API_KEY
  2. Google Cloud TTS if GOOGLE_TTS_KEY set — en-US-Neural2-D
  3. pyttsx3 (local, instant, robotic but always works)
  4. Print only (text mode)
"""

import os
import sys

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam
GOOGLE_TTS_KEY = os.environ.get("GOOGLE_TTS_KEY", "")


def speak(text: str, voice: bool = False):
    """Speak text aloud if voice=True, otherwise just print."""
    if not voice or not text.strip():
        return

    if ELEVENLABS_API_KEY and _speak_elevenlabs(text):
        return
    if GOOGLE_TTS_KEY and _speak_google_tts(text):
        return
    if _speak_pyttsx3(text):
        return

    print(f"[TTS] (no audio backend): {text}")


# ── ElevenLabs (streaming) ────────────────────────────────────────────────────
def _speak_elevenlabs(text: str) -> bool:
    try:
        import urllib.request
        import json
        import tempfile

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"
        payload = json.dumps({
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
                "style": 0.2,
                "use_speaker_boost": True,
            },
        }).encode()

        req = urllib.request.Request(url, data=payload, headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        })

        with urllib.request.urlopen(req, timeout=20) as r:
            audio = r.read()

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio)
            tmp = f.name

        _play_audio(tmp)
        os.unlink(tmp)
        return True

    except Exception as e:
        print(f"[TTS/ElevenLabs] {e}")
        return False


# ── Google Cloud TTS ──────────────────────────────────────────────────────────
def _speak_google_tts(text: str) -> bool:
    try:
        import urllib.request
        import json
        import base64
        import tempfile

        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_TTS_KEY}"
        payload = json.dumps({
            "input": {"text": text},
            "voice": {"languageCode": "en-US", "name": "en-US-Neural2-D"},
            "audioConfig": {"audioEncoding": "MP3"},
        }).encode()

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())

        audio = base64.b64decode(data["audioContent"])
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio)
            tmp = f.name

        _play_audio(tmp)
        os.unlink(tmp)
        return True

    except Exception as e:
        print(f"[TTS/GoogleTTS] {e}")
        return False


# ── Coqui TTS ─────────────────────────────────────────────────────────────────
def _speak_coqui(text: str) -> bool:
    try:
        from TTS.api import TTS
        import tempfile

        if not hasattr(_speak_coqui, "_tts"):
            print("[TTS] Loading Coqui model (first run)...")
            _speak_coqui._tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name

        _speak_coqui._tts.tts_to_file(text=text, file_path=tmp)
        _play_audio(tmp)
        os.unlink(tmp)
        return True

    except ImportError:
        return False
    except Exception as e:
        print(f"[TTS/Coqui] {e}")
        return False


# ── pyttsx3 ───────────────────────────────────────────────────────────────────
def _speak_pyttsx3(text: str) -> bool:
    try:
        import pyttsx3
        if not hasattr(_speak_pyttsx3, "_engine"):
            _speak_pyttsx3._engine = pyttsx3.init()
            _speak_pyttsx3._engine.setProperty("rate", 175)
        engine = _speak_pyttsx3._engine
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        print(f"[TTS/pyttsx3] {e}")
        return False


# ── Audio playback ────────────────────────────────────────────────────────────
def _play_audio(path: str):
    import subprocess
    if sys.platform == "darwin":
        subprocess.run(["afplay", path], check=True)
    elif sys.platform.startswith("linux"):
        for player in ["aplay", "paplay", "mpg123", "ffplay"]:
            try:
                subprocess.run([player, path], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
    elif sys.platform == "win32":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
