"""
server.py — Jarvis FastAPI web server.
Exposes Jarvis via REST + WebSocket. Serves the mobile PWA frontend.
Single worker, single Jarvis instance (shared state across connections).
"""

import asyncio
import io
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jarvis import Jarvis

app = FastAPI(title="Jarvis", docs_url=None, redoc_url=None)

_jarvis: Jarvis | None = None
_start_time = time.time()
_ws_clients: set[asyncio.Queue] = set()
_init_error: str = ""

JARVIS_ACCESS_TOKEN = os.environ.get("JARVIS_ACCESS_TOKEN", "")
PRIVACY_MODE = os.environ.get("PRIVACY_MODE", "false").lower() == "true"
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam
GOOGLE_TTS_KEY = os.environ.get("GOOGLE_TTS_KEY", "")
WHISPER_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "auto")

_GOOGLE_TTS_VOICES = {
    "si": {"languageCode": "si-LK", "name": "si-LK-Standard-A"},
    "en": {"languageCode": "en-US", "name": "en-US-Neural2-D"},
}


def _detect_lang(text: str) -> str:
    """Return 'si' if text contains Sinhala script, else 'en'."""
    import re
    return "si" if re.search(r'[඀-෿]', text) else "en"


def _whisper_lang() -> str | None:
    lang = WHISPER_LANGUAGE.strip().lower()
    return None if lang in ("auto", "", "none") else lang


# ── Suppress access logs for chat/ws routes (contain conversation content) ─────

class _SuppressChatLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/api/chat" not in msg and " /ws" not in msg

logging.getLogger("uvicorn.access").addFilter(_SuppressChatLog())


# ── Auth ──────────────────────────────────────────────────────────────────────

def _check_token(token: str) -> bool:
    if not JARVIS_ACCESS_TOKEN:
        return True
    return token == JARVIS_ACCESS_TOKEN


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        token = request.headers.get("X-Jarvis-Token", "")
        if not _check_token(token):
            return JSONResponse({"error": "Unauthorized — set X-Jarvis-Token header"}, status_code=401)
    return await call_next(request)


# ── Jarvis instance ───────────────────────────────────────────────────────────

def get_jarvis() -> Jarvis:
    global _jarvis, _init_error
    if _jarvis is None:
        try:
            _jarvis = Jarvis(voice_mode=False)
            from tools.system_tool import set_broadcast
            set_broadcast(_broadcast_alert)
            _init_error = ""
        except ValueError as exc:
            _init_error = str(exc)
            raise
    return _jarvis


def _broadcast_alert(message: str):
    dead = set()
    for q in _ws_clients:
        try:
            q.put_nowait({"type": "alert", "content": message})
        except Exception:
            dead.add(q)
    _ws_clients.difference_update(dead)


def _jarvis_or_503():
    try:
        return get_jarvis()
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail=_init_error or "GEMINI_API_KEY not set. Add it in Railway → Variables.",
        )


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    if JARVIS_ACCESS_TOKEN:
        print(f"\n{'='*60}\n🔒 Auth enabled — X-Jarvis-Token required on all /api/* routes\n{'='*60}\n")
    else:
        print(f"\n{'='*60}\n⚠️  No JARVIS_ACCESS_TOKEN set — API is open. Set it in Railway Variables.\n{'='*60}\n")

    if PRIVACY_MODE:
        print("[Jarvis] PRIVACY_MODE=true — email bodies will not be sent to Gemini API")

    try:
        j = get_jarvis()
        j._alert_queues = _ws_clients
        asyncio.create_task(j.proactive_check())
    except ValueError as exc:
        print(f"\n{'='*60}\n⚠️  JARVIS NOT READY\n{exc}\n{'='*60}\n")


# ── REST Endpoints ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class TTSRequest(BaseModel):
    text: str


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    if not req.message.strip():
        return JSONResponse({"error": "empty message"}, status_code=400)
    j = _jarvis_or_503()
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, j.chat, req.message.strip(), True)
    return {"response": response, "turns": len(j.conversation) // 2}


@app.get("/api/status")
async def status():
    if _init_error:
        return JSONResponse({"status": "error", "error": _init_error}, status_code=503)
    j = get_jarvis()
    from tools.registry import TOOLS
    uptime_s = int(time.time() - _start_time)
    h, m, s = uptime_s // 3600, (uptime_s % 3600) // 60, uptime_s % 60
    return {
        "status": "online",
        "model": "gemini-2.5-flash",
        "tools": [t["name"] for t in TOOLS],
        "tool_count": len(TOOLS),
        "memory_facts": len(j.memory.get_all_facts()),
        "conversation_turns": len(j.conversation) // 2,
        "uptime": f"{h}h {m}m {s}s",
        "connected_clients": len(_ws_clients),
        "privacy_mode": PRIVACY_MODE,
        "auth_enabled": bool(JARVIS_ACCESS_TOKEN),
    }


@app.delete("/api/conversation")
async def clear_conversation():
    get_jarvis().conversation.clear()
    return {"cleared": True}


@app.get("/api/conversation")
async def get_conversation():
    j = get_jarvis()
    turns = []
    for c in j.conversation:
        role = c.role
        text_parts = [p.text for p in c.parts if p.text is not None]
        if text_parts:
            turns.append({"role": role, "text": " ".join(text_parts)})
    return {"turns": turns, "count": len(turns)}


@app.get("/api/memory")
async def get_memory():
    if JARVIS_ACCESS_TOKEN == "" and not os.environ.get("JARVIS_ACCESS_TOKEN"):
        return JSONResponse({"error": "JARVIS_ACCESS_TOKEN not set — /api/memory is disabled"}, status_code=503)
    facts = get_jarvis().memory.get_all_facts()
    return {"facts": facts, "count": len(facts)}


@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest):
    from fastapi import HTTPException
    import re, json as _json, urllib.request

    if not GOOGLE_TTS_KEY and not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="No TTS configured. Set GOOGLE_TTS_KEY or ELEVENLABS_API_KEY.")

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    # Strip markdown
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'https?://\S+', 'the link', text)
    text = re.sub(r'[*_#]', '', text)
    text = re.sub(r'\n+', ' ', text).strip()

    lang = _detect_lang(text)

    # Sinhala → Google TTS (ElevenLabs has no Sinhala support)
    if lang == "si" or (GOOGLE_TTS_KEY and not ELEVENLABS_API_KEY):
        if not GOOGLE_TTS_KEY:
            raise HTTPException(status_code=503, detail="Sinhala TTS requires GOOGLE_TTS_KEY")
        voice = _GOOGLE_TTS_VOICES.get(lang, _GOOGLE_TTS_VOICES["en"])
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_TTS_KEY}"
        payload = _json.dumps({
            "input": {"text": text},
            "voice": voice,
            "audioConfig": {"audioEncoding": "MP3"},
        }).encode()
        try:
            req_obj = urllib.request.Request(url, data=payload,
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req_obj, timeout=15) as resp:
                import base64
                audio_data = base64.b64decode(_json.loads(resp.read())["audioContent"])
            return StreamingResponse(
                io.BytesIO(audio_data),
                media_type="audio/mpeg",
                headers={"Content-Disposition": "inline; filename=response.mp3",
                         "X-Detected-Language": lang},
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Google TTS error: {e}")

    # English → ElevenLabs
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY not configured")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"
    payload = _json.dumps({
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8,
                           "style": 0.2, "use_speaker_boost": True},
    }).encode()
    try:
        req_obj = urllib.request.Request(url, data=payload, headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        })
        with urllib.request.urlopen(req_obj, timeout=20) as resp:
            audio_data = resp.read()
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=response.mp3",
                     "X-Detected-Language": lang},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {e}")


@app.post("/api/stt")
async def stt_endpoint(request: Request):
    try:
        import whisper as _whisper
    except ImportError:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Whisper not installed. Run: pip install openai-whisper")

    import tempfile
    body = await request.body()
    content_type = request.headers.get("content-type", "audio/webm")
    suffix = ".webm" if "webm" in content_type else ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(body)
        tmp_path = f.name

    try:
        loop = asyncio.get_event_loop()
        model = await loop.run_in_executor(None, _whisper.load_model, "base")
        lang = _whisper_lang()
        transcribe_fn = lambda: model.transcribe(tmp_path, language=lang)
        result = await loop.run_in_executor(None, transcribe_fn)
        return {
            "transcript": result["text"].strip(),
            "detected_language": result.get("language", lang or "unknown"),
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Whisper error: {e}")
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass


# ── Google OAuth callback ─────────────────────────────────────────────────────

@app.get("/auth/callback")
async def google_oauth_callback(code: str = "", error: str = ""):
    if error:
        return JSONResponse({"error": error}, status_code=400)
    if not code:
        return JSONResponse({"error": "No code provided"}, status_code=400)
    return JSONResponse({
        "message": "OAuth code received. For Railway deployment, run auth/google_oauth.py locally.",
        "code": code,
    })


@app.get("/auth/spotify")
async def spotify_oauth_callback(code: str = "", error: str = ""):
    if error:
        return JSONResponse({"error": error}, status_code=400)
    return JSONResponse({
        "message": "Spotify OAuth code received. Run auth/spotify_oauth.py locally for setup.",
        "code": code,
    })


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    if JARVIS_ACCESS_TOKEN and not _check_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    if _init_error:
        await websocket.send_json({"type": "error", "content": _init_error})
        await websocket.close()
        return

    jarvis = get_jarvis()
    q: asyncio.Queue = asyncio.Queue()
    _ws_clients.add(q)

    async def _send_alerts():
        while True:
            alert = await q.get()
            try:
                await websocket.send_json(alert)
            except Exception:
                break

    alert_task = asyncio.create_task(_send_alerts())

    try:
        while True:
            data = await websocket.receive_json()
            message = (data.get("message") or data.get("content") or "").strip()
            if not message:
                continue
            await websocket.send_json({"type": "thinking"})
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, jarvis.chat, message, True)
            await websocket.send_json({
                "type": "response",
                "content": response,
                "turns": len(jarvis.conversation) // 2,
            })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
    finally:
        alert_task.cancel()
        _ws_clients.discard(q)


# ── Static Files (PWA) ────────────────────────────────────────────────────────

WEB_DIR = Path(__file__).parent / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import socket
    import uvicorn

    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8080))

    local_ip = "localhost"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    tailscale_ip = ""
    try:
        import subprocess
        result = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=3)
        tailscale_ip = result.stdout.strip().splitlines()[0] if result.returncode == 0 else ""
    except Exception:
        pass

    print("\n" + "═" * 52)
    print("  J.A.R.V.I.S  —  Online")
    print("═" * 52)
    print(f"  Local:     http://localhost:{port}")
    print(f"  Network:   http://{local_ip}:{port}")
    if tailscale_ip:
        print(f"  Tailscale: http://{tailscale_ip}:{port}  ← use this on phone")
    print(f"\n  API:       http://{local_ip}:{port}/api/status")
    print("═" * 52 + "\n")

    uvicorn.run("server:app", host=host, port=port, workers=1)
