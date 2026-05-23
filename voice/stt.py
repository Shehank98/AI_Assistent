"""
voice/stt.py — Speech-to-text using OpenAI Whisper (runs locally)

Install:  pip install openai-whisper pyaudio
Optional: pip install pvporcupine  (for wake-word detection)
"""

import os
import sys

WHISPER_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "auto")


def _whisper_lang() -> str | None:
    """Return Whisper language code or None for auto-detect."""
    lang = WHISPER_LANGUAGE.strip().lower()
    if lang in ("auto", "", "none"):
        return None  # Whisper auto-detects
    return lang  # e.g. "si", "en", "ta"


# ── Lazy imports so text mode works without audio deps ────────────────────────
def listen(wake_word: bool = False, timeout: int = 10) -> str | None:
    """
    Record from mic and return transcribed text.
    Set wake_word=True to wait for 'Hey Jarvis' first (requires porcupine).
    Returns None if nothing detected or on error.
    """
    try:
        import whisper
        import pyaudio
        import wave
        import tempfile
        import os
        import numpy as np
    except ImportError:
        print("[STT] Missing deps. Install: pip install openai-whisper pyaudio numpy")
        return input("You (text fallback): ").strip() or None

    # Load Whisper once (cached after first call)
    if not hasattr(listen, "_model"):
        print("[STT] Loading Whisper model (first run only)...")
        listen._model = whisper.load_model("base")  # tiny/base/small/medium/large

    if wake_word:
        _wait_for_wake_word()

    print("[STT] Listening... (speak now)")
    audio_data = _record_audio(timeout=timeout)
    if audio_data is None:
        return None

    # Save to temp WAV and transcribe
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
        _save_wav(f.name, audio_data)

    try:
        result = listen._model.transcribe(tmp_path, language=_whisper_lang())
        text = result["text"].strip()
        print(f"[STT] Heard: {text}")
        return text if text else None
    finally:
        os.unlink(tmp_path)


def _record_audio(
    timeout: int = 10,
    sample_rate: int = 16000,
    chunk: int = 1024,
    channels: int = 1,
    silence_threshold: float = 300,
    silence_duration: float = 1.5,
) -> list | None:
    """Record until silence or timeout."""
    import pyaudio
    import numpy as np

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=sample_rate,
        input=True,
        frames_per_buffer=chunk,
    )

    frames = []
    silent_chunks = 0
    max_chunks = int(sample_rate / chunk * timeout)
    silence_limit = int(sample_rate / chunk * silence_duration)

    for _ in range(max_chunks):
        data = stream.read(chunk, exception_on_overflow=False)
        frames.append(data)
        amplitude = max(abs(int.from_bytes(data[i:i+2], 'little', signed=True))
                       for i in range(0, len(data), 2))
        if amplitude < silence_threshold:
            silent_chunks += 1
        else:
            silent_chunks = 0
        if silent_chunks > silence_limit and len(frames) > silence_limit:
            break

    stream.stop_stream()
    stream.close()
    pa.terminate()
    return frames if len(frames) > silence_limit else None


def _save_wav(path: str, frames: list, sample_rate: int = 16000, channels: int = 1):
    import wave
    import pyaudio
    wf = wave.open(path, "wb")
    wf.setnchannels(channels)
    wf.setsampwidth(2)  # paInt16
    wf.setframerate(sample_rate)
    wf.writeframes(b"".join(frames))
    wf.close()


def _wait_for_wake_word():
    """Wait for 'Hey Jarvis' using Picovoice Porcupine."""
    try:
        import pvporcupine
        import pyaudio
        import struct
    except ImportError:
        print("[Wake] pvporcupine not installed. Skipping wake word.")
        return

    porcupine = pvporcupine.create(keywords=["jarvis"])
    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length,
    )
    print("[Wake] Waiting for 'Hey Jarvis'...")
    try:
        while True:
            pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            if porcupine.process(pcm) >= 0:
                print("[Wake] Wake word detected!")
                break
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        porcupine.delete()
