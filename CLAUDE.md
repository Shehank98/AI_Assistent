# CLAUDE.md — Jarvis AI Assistant

Personal AI assistant powered by Claude. Runs on your PC, accessible from any device (phone, tablet, browser) — voice or text.

---

## Architecture

```
Phone/Browser ──WebSocket──▶ server.py ──▶ Jarvis class ──▶ Claude API (claude-sonnet-4-6)
Desktop Mic ──────────────▶ jarvis.py ──▶ Jarvis class ──▶ Claude API
                Both share: MemoryStore (SQLite at ~/.jarvis/memory.db)
```

- **Web/mobile mode**: `server.py` hosts a FastAPI server + PWA frontend. One Jarvis instance shared across all browser connections.
- **Desktop voice mode**: `jarvis.py` runs a local voice loop (Whisper STT + TTS).
- **Memory**: Facts persist in SQLite across restarts and sessions. Conversation history resets per session.

---

## Directory Structure

```
AI_Assistent/
├── jarvis.py          Core orchestrator — Jarvis class, agentic loop, CLI entry point
├── server.py          FastAPI web server — REST API + WebSocket + static file serving
├── start.sh           Launcher — starts web server (+ optional voice loop)
├── requirements.txt   Python dependencies
├── .env.example       Environment variable template
├── CLAUDE.md          This file
├── tools/
│   ├── registry.py    All tool definitions + implementations + dispatcher
│   └── __init__.py
├── voice/
│   ├── stt.py         Speech-to-text (Whisper + pyaudio + wake word)
│   ├── tts.py         Text-to-speech (ElevenLabs → Coqui → pyttsx3 cascade)
│   └── __init__.py
├── memory/
│   ├── store.py       SQLite-backed persistent memory
│   └── __init__.py
└── web/               Mobile PWA frontend (served by server.py)
    ├── index.html
    ├── app.js
    ├── style.css
    └── manifest.json
```

---

## Quick Start

```bash
# 1. Clone and enter the project
cd AI_Assistent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your API key
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-...

# 4. Start the web server
./start.sh

# 5. Open in browser
# Local:  http://localhost:8080
# Phone:  http://<your-PC-IP>:8080
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | — | Your Anthropic API key |
| `ELEVENLABS_API_KEY` | No | — | ElevenLabs key for best voice quality |
| `ELEVENLABS_VOICE_ID` | No | Rachel | ElevenLabs voice to use |
| `PORT` | No | `8080` | Web server port |

---

## Running Jarvis

### Web/Mobile Mode (recommended)
```bash
./start.sh
# Then open http://localhost:8080 in any browser
```

### Desktop Text Mode
```bash
python jarvis.py
# Interactive REPL in your terminal
```

### Desktop Voice Mode (requires pyaudio + whisper)
```bash
pip install openai-whisper pyaudio pyttsx3
python jarvis.py --voice
# Say "Hey Jarvis" to activate (or adjust wake word in voice/stt.py)
```

### Web Server + Voice Loop Together
```bash
./start.sh --with-voice
# Web server on :8080, voice loop running in background
```

### Web Server (manual, with hot-reload for development)
```bash
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

---

## Mobile Access

### Same WiFi (local network)
1. Find your PC's IP: `hostname -I` (Linux) or `ipconfig` (Windows)
2. Open `http://<PC-IP>:8080` in Chrome on your phone
3. Tap "Add to Home Screen" for a Jarvis app icon (PWA)

### From Anywhere (Tailscale — free, recommended)

Tailscale gives your PC and phone a private network accessible from anywhere, with HTTPS — which is required for voice input on Android Chrome.

**Setup (one-time):**
```bash
# On your PC (Linux):
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Get your Tailscale hostname:
tailscale status | head -3
```
1. Install the **Tailscale** app on your phone (iOS/Android)
2. Sign in with the same account on both devices
3. Your PC will have a hostname like `my-pc.tail1234.ts.net`

**Enable HTTPS (unlocks voice on Android Chrome):**
```bash
sudo tailscale cert my-pc.tail1234.ts.net
# Then run Jarvis with uvicorn + SSL (see Tailscale docs for cert paths)
```

**Access URL:** `https://my-pc.tail1234.ts.net:8080`

### Voice Input on Mobile
- **Android**: Works in Chrome when on HTTPS (Tailscale) — tap the 🎤 button
- **iOS**: Works in Safari (HTTP is fine on iOS)
- **Fallback**: If voice isn't available, the mic button hides and you type instead

---

## Tools Reference

| Tool | Description | Free? |
|---|---|---|
| `read_file` | Read any file from disk | ✓ |
| `write_file` | Write/create files on disk | ✓ |
| `list_directory` | Browse directories | ✓ |
| `run_shell` | Execute shell commands | ✓ |
| `web_search` | DuckDuckGo instant answers (no key) | ✓ |
| `get_weather` | Current weather via wttr.in (no key) | ✓ |
| `get_datetime` | Current date and time | ✓ |
| `open_url` | Open URLs in the browser | ✓ |
| `remember_fact` | Save a user fact to persistent memory | ✓ |
| `recall_facts` | Retrieve all saved facts | ✓ |
| `set_timer` | Countdown timer with audio alert | ✓ |
| `create_note` | Save a markdown note to ~/Notes/ | ✓ |
| `list_notes` | List all saved notes | ✓ |
| `read_note` | Read a saved note by title | ✓ |

---

## Adding New Tools

1. Open `tools/registry.py`
2. Add a tool definition to the `TOOLS` list (Claude API format):
```python
{
    "name": "my_tool",
    "description": "What it does — be specific, Claude uses this to decide when to call it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "What this param is"}
        },
        "required": ["param"],
    },
},
```
3. Add the implementation function:
```python
def _my_tool(param: str) -> str:
    # do the work
    return "result as string"
```
4. Add to `TOOL_MAP`:
```python
"my_tool": lambda inp: _my_tool(inp["param"]),
```

That's it. Claude will automatically discover and use the new tool.

---

## Memory System

Facts are stored in SQLite at `~/.jarvis/memory.db` and persist across restarts.

**How to use it:**
- Tell Jarvis to remember something: *"Remember that I prefer dark mode"*
- Jarvis uses `remember_fact` tool automatically when you say things like "remember...", "my name is...", "I always..."
- Facts are injected into every Claude request as context

**Inspect the database:**
```bash
sqlite3 ~/.jarvis/memory.db "SELECT key, value FROM facts;"
```

**Clear all facts:**
```bash
sqlite3 ~/.jarvis/memory.db "DELETE FROM facts;"
```

---

## API Reference

The server exposes a simple REST + WebSocket API if you want to integrate with other tools.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | Send a message, get a response. Body: `{"message": "..."}` |
| `GET` | `/api/status` | Health check + conversation stats |
| `DELETE` | `/api/conversation` | Clear conversation history (keeps memory/facts) |
| `WS` | `/ws` | Real-time WebSocket — send `{"message": "..."}`, receive `{"type": "thinking"}` / `{"type": "response", "message": "..."}` |

---

## Troubleshooting

**`ANTHROPIC_API_KEY` not found**
Make sure `.env` exists with the key, or `export ANTHROPIC_API_KEY=sk-ant-...` in your shell.

**Port 8080 already in use**
```bash
PORT=9090 ./start.sh
```

**Voice input not working on Android**
Chrome on Android requires HTTPS for the microphone. Use Tailscale (see Mobile Access above) or type instead — typing always works.

**Whisper/pyaudio import errors (voice mode)**
```bash
pip install openai-whisper
# Linux:
sudo apt install portaudio19-dev && pip install pyaudio
# Mac:
brew install portaudio && pip install pyaudio
```

**`ModuleNotFoundError: fastapi`**
```bash
pip install -r requirements.txt
```

---

## Roadmap

- [ ] Tailscale auto-HTTPS setup script
- [ ] Push notifications to mobile when a timer fires
- [ ] Calendar integration (CalDAV — free, works with Google/iCloud)
- [ ] Semantic memory with ChromaDB (find facts by meaning, not just key)
- [ ] Multi-user support (separate conversation contexts per user)
- [ ] Wake word on desktop (`pvporcupine` — free tier)
- [ ] Streaming responses (show Jarvis typing in real-time)
