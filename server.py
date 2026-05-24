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


def _broadcast_alert(message):
    """Broadcast alert or dict payload to all connected WS clients."""
    payload = message if isinstance(message, dict) else {"type": "alert", "content": message}
    dead = set()
    for q in _ws_clients:
        try:
            q.put_nowait(payload)
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

        # Wire approval broadcast
        from agent.approval import set_broadcast as _set_approval_broadcast
        _set_approval_broadcast(_broadcast_alert)

        # Start background scheduler (proactive checks, routines, world state)
        from agent.scheduler import setup_scheduler
        setup_scheduler(j)

        # Kick off first world-state build
        from agent.observer import refresh_world_state
        asyncio.create_task(refresh_world_state(j.memory))

        # Set up pgvector RAG store (no-op if DATABASE_URL not set)
        if os.environ.get("DATABASE_URL"):
            try:
                from rag.store import setup as rag_setup
                await asyncio.get_event_loop().run_in_executor(None, rag_setup)
            except Exception as exc:
                print(f"[rag] pgvector setup failed (run CREATE EXTENSION vector in Railway DB console): {exc}")

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


@app.get("/api/agent/status")
async def agent_status():
    """WorldState + self-monitor health — used by the settings panel."""
    from agent.observer import get_world_state
    from agent.self_monitor import health_check
    j = get_jarvis()
    ws = get_world_state()
    health = health_check(j.memory)
    return {
        "world_state": {
            "built_at": ws.built_at.isoformat() if ws.built_at else None,
            "time_of_day": ws.time_of_day,
            "weather": ws.weather,
            "upcoming_events": ws.upcoming_events,
            "tasks_due_today": ws.tasks_due_today,
            "active_goals": [g["description"] for g in ws.active_goals],
        },
        "health": health,
    }


@app.get("/api/goals")
async def get_goals(status: str = "active"):
    valid = {"active", "completed", "cancelled", "all"}
    if status not in valid:
        return JSONResponse({"error": f"status must be one of {valid}"}, status_code=400)
    goals = get_jarvis().memory.list_goals(None if status == "all" else status)
    return {"goals": goals, "count": len(goals)}


@app.delete("/api/goals/{goal_id}")
async def cancel_goal_endpoint(goal_id: int):
    get_jarvis().memory.update_goal(goal_id, status="cancelled")
    return {"cancelled": goal_id}


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


@app.post("/api/upload")
async def upload_document(request: Request):
    """
    Upload a document into the RAG knowledge base.
    Send file bytes as the body; set X-Filename header to the original filename.
    Supports: .xlsx, .xls, .csv, .pdf, .txt, .md
    """
    import tempfile
    from fastapi import HTTPException

    if not os.environ.get("DATABASE_URL"):
        raise HTTPException(status_code=503, detail="RAG store unavailable — DATABASE_URL not set.")

    filename = request.headers.get("X-Filename", "upload.bin").strip()
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty file body.")

    suffix = Path(filename).suffix or ".bin"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(body)
        tmp_path = tmp.name

    try:
        from rag.ingest import ingest_file
        loop = asyncio.get_event_loop()
        chunk_count, fmt = await loop.run_in_executor(None, ingest_file, tmp_path)
        return {
            "filename": filename,
            "format": fmt,
            "chunks": chunk_count,
            "message": f"Indexed {chunk_count} chunks from '{filename}'. Ask Jarvis about it.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.get("/api/documents")
async def list_documents_endpoint():
    """List all documents indexed in the RAG knowledge base."""
    if not os.environ.get("DATABASE_URL"):
        return JSONResponse({"error": "RAG store unavailable"}, status_code=503)
    try:
        from rag.store import list_sources
        sources = list_sources()
        return {"documents": sources, "count": len(sources)}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


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
    alert_q: asyncio.Queue = asyncio.Queue()  # outbound alerts/approvals
    msg_q: asyncio.Queue = asyncio.Queue()    # inbound user messages
    _ws_clients.add(alert_q)

    async def _send_alerts():
        """Push queued alerts/approvals to client continuously."""
        while True:
            payload = await alert_q.get()
            try:
                await websocket.send_json(payload)
            except Exception:
                break

    async def _recv_loop():
        """
        Continuously receive WS frames — runs CONCURRENTLY with the Jarvis executor.
        This is what allows approval_response to arrive while Jarvis is mid-turn.
        """
        while True:
            try:
                data = await websocket.receive_json()
                if data.get("type") == "approval_response":
                    from agent.approval import respond_approval
                    respond_approval(
                        data.get("approval_id", ""),
                        bool(data.get("granted", False)),
                    )
                else:
                    await msg_q.put(data)
            except Exception:
                await msg_q.put(None)   # sentinel — signals connection closed
                break

    alert_task = asyncio.create_task(_send_alerts())
    recv_task  = asyncio.create_task(_recv_loop())

    try:
        while True:
            data = await msg_q.get()
            if data is None:
                break   # connection closed

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

            async def _extract(u=message, r=response):
                try:
                    from agent.memory_engine import extract_from_conversation
                    await loop.run_in_executor(
                        None, extract_from_conversation, u, r, jarvis._client, jarvis.memory
                    )
                except Exception:
                    pass
            asyncio.create_task(_extract())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
    finally:
        alert_task.cancel()
        recv_task.cancel()
        _ws_clients.discard(alert_q)


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
