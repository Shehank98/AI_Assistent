"""
server.py — Jarvis FastAPI web server.
Exposes Jarvis via REST + WebSocket. Serves the mobile PWA frontend.
Single worker, single Jarvis instance (shared state across connections).
"""

import asyncio
import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jarvis import Jarvis

app = FastAPI(title="Jarvis", docs_url=None, redoc_url=None)

_jarvis: Jarvis | None = None
_start_time = time.time()
_ws_clients: set[asyncio.Queue] = set()


def get_jarvis() -> Jarvis:
    global _jarvis
    if _jarvis is None:
        _jarvis = Jarvis(voice_mode=False)
        # Wire timer alerts to WebSocket broadcast
        from tools.system_tool import set_broadcast
        set_broadcast(_broadcast_alert)
    return _jarvis


def _broadcast_alert(message: str):
    """Push an alert message to all connected WebSocket clients."""
    dead = set()
    for q in _ws_clients:
        try:
            q.put_nowait({"type": "alert", "content": message})
        except Exception:
            dead.add(q)
    _ws_clients.difference_update(dead)


# ── Startup / Proactive Check ──────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    j = get_jarvis()
    j._alert_queues = _ws_clients  # type: ignore[assignment]
    asyncio.create_task(j.proactive_check())


# ── REST Endpoints ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    if not req.message.strip():
        return JSONResponse({"error": "empty message"}, status_code=400)
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, get_jarvis().chat, req.message.strip(), True
    )
    j = get_jarvis()
    return {"response": response, "turns": len(j.conversation) // 2}


@app.get("/api/status")
async def status():
    j = get_jarvis()
    from tools.registry import TOOLS
    uptime_s = int(time.time() - _start_time)
    h, m, s = uptime_s // 3600, (uptime_s % 3600) // 60, uptime_s % 60
    return {
        "status": "online",
        "model": "gemini-2.0-flash",
        "tools": [t["name"] for t in TOOLS],
        "tool_count": len(TOOLS),
        "memory_facts": len(j.memory.get_all_facts()),
        "conversation_turns": len(j.conversation) // 2,
        "uptime": f"{h}h {m}m {s}s",
        "connected_clients": len(_ws_clients),
    }


@app.delete("/api/conversation")
async def clear_conversation():
    get_jarvis().conversation.clear()
    return {"cleared": True}


@app.get("/api/memory")
async def get_memory():
    facts = get_jarvis().memory.get_all_facts()
    return {"facts": facts, "count": len(facts)}


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
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    jarvis = get_jarvis()

    # Register this client's alert queue
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
            response = await loop.run_in_executor(
                None, jarvis.chat, message, True
            )
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
