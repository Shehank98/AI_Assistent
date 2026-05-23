"""
server.py — Jarvis FastAPI web server
Exposes Jarvis over HTTP + WebSocket so you can control it from any device.
Run: python server.py   (or: uvicorn server:app --host 0.0.0.0 --port 8080)
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jarvis import Jarvis

app = FastAPI(title="Jarvis API", docs_url=None, redoc_url=None)

# Single shared instance — all clients share conversation context.
# This is intentional: one Jarvis, one memory, one brain.
_jarvis: Jarvis | None = None


def get_jarvis() -> Jarvis:
    global _jarvis
    if _jarvis is None:
        _jarvis = Jarvis(voice_mode=False)
    return _jarvis


# ── HTTP Endpoints ────────────────────────────────────────────────────────────

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
    return {
        "response": response,
        "turns": len(get_jarvis().conversation) // 2,
    }


@app.get("/api/status")
async def status():
    j = get_jarvis()
    return {
        "status": "online",
        "model": "claude-sonnet-4-6",
        "turns": len(j.conversation) // 2,
    }


@app.delete("/api/conversation")
async def clear_conversation():
    get_jarvis().conversation.clear()
    return {"cleared": True}


# ── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    jarvis = get_jarvis()
    try:
        while True:
            data = await websocket.receive_json()
            message = (data.get("message") or "").strip()
            if not message:
                continue
            await websocket.send_json({"type": "thinking"})
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, jarvis.chat, message, True
            )
            await websocket.send_json({
                "type": "response",
                "message": response,
                "turns": len(jarvis.conversation) // 2,
            })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ── Static Files (PWA frontend) ───────────────────────────────────────────────

WEB_DIR = Path(__file__).parent / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8080))

    local_ip = "localhost"
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print("═" * 50)
    print("  JARVIS — Web Server Starting")
    print("═" * 50)
    print(f"  Local:   http://localhost:{port}")
    print(f"  Network: http://{local_ip}:{port}")
    print(f"  API:     http://{local_ip}:{port}/api/status")
    print()
    print("  Mobile: open the Network URL in Chrome on your phone")
    print("  For remote access from anywhere: see CLAUDE.md → Tailscale")
    print("═" * 50)

    uvicorn.run("server:app", host=host, port=port, workers=1)
