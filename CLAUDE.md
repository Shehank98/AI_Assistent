# CLAUDE.md — Jarvis AI Assistant

Personal AI assistant powered by Claude. Runs on your PC or Railway, accessible from any device (phone, tablet, browser) — voice or text. Talks like a smart friend, not a corporate chatbot.

---

## Architecture

```
Phone/Browser ──WebSocket──▶ server.py ──▶ Jarvis class ──▶ Claude API (claude-sonnet-4-6)
Desktop Mic ──────────────▶ jarvis.py ──▶ Jarvis class ──▶ Claude API
                Both share: MemoryStore (SQLite at ~/.jarvis/memory.db)

Proactive alerts:
server.py background task ──▶ gmail_important_check / calendar_upcoming / list_tasks_due_today
                           ──▶ WebSocket broadcast ──▶ Phone notification banner
```

---

## Directory Structure

```
AI_Assistent/
├── jarvis.py              Core orchestrator — Jarvis class, agentic loop, CLI
├── server.py              FastAPI web server — REST + WebSocket + PWA
├── start.sh               Launcher — web server (+ optional voice)
├── requirements.txt       Python dependencies
├── .env.example           Environment variable template
├── railway.toml           Railway deployment config
├── Procfile               Heroku/Railway process definition
├── CLAUDE.md              This file
│
├── auth/
│   ├── google_oauth.py    Google OAuth2 helper (Gmail + Calendar)
│   └── spotify_oauth.py   Spotify OAuth helper
│
├── tools/
│   ├── registry.py        Central tool registry + dispatcher
│   ├── gmail_tool.py      Gmail: read, search, send, reply
│   ├── calendar_tool.py   Google Calendar: today, week, create, delete
│   ├── spotify_tool.py    Spotify: play, pause, skip, volume, queue
│   ├── whatsapp_tool.py   WhatsApp via pywhatkit (desktop only)
│   ├── news_tool.py       News via NewsAPI (RSS fallback, no key needed)
│   ├── memory_tool.py     Facts + task management (SQLite)
│   ├── web_tool.py        Web search, fetch, YouTube, Wikipedia
│   └── system_tool.py     Weather, time, timers, notes, files, shell
│
├── memory/
│   └── store.py           SQLite memory (facts + tasks + conversations)
│
├── voice/
│   ├── stt.py             Speech-to-text (Whisper + wake word)
│   └── tts.py             Text-to-speech (ElevenLabs → Coqui → pyttsx3)
│
└── web/                   Mobile PWA frontend
    ├── index.html
    ├── app.js
    ├── style.css
    └── manifest.json
```

---

## Quick Start (local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
cp .env.example .env
# Edit .env → add ANTHROPIC_API_KEY=sk-ant-...

# 3. Start
./start.sh

# 4. Open in browser
# Local:  http://localhost:8080
# Phone:  http://<your-PC-IP>:8080
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | Your Anthropic API key |
| `GOOGLE_CLIENT_ID` | For Gmail/Calendar | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For Gmail/Calendar | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | For Gmail/Calendar | OAuth callback URL |
| `GOOGLE_TOKEN_B64` | Railway only | base64 of `~/.jarvis/gmail_token.json` |
| `SPOTIFY_CLIENT_ID` | For Spotify | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | For Spotify | Spotify app client secret |
| `SPOTIFY_REDIRECT_URI` | For Spotify | Spotify OAuth callback URL |
| `SPOTIFY_TOKEN_B64` | Railway only | base64 of `~/.jarvis/spotify_token.json` |
| `NEWS_API_KEY` | No | newsapi.org key (free, falls back to RSS) |
| `JARVIS_LOCATION` | No | Default city for weather (e.g. `Colombo, Sri Lanka`) |
| `DESKTOP_MODE` | No | `true` to enable WhatsApp + shell + open_url |
| `ELEVENLABS_API_KEY` | No | ElevenLabs for high-quality TTS |
| `PORT` | No | Server port (default 8080, Railway sets automatically) |

---

## Running Modes

### Web/Mobile Mode (recommended)
```bash
./start.sh
# Open http://localhost:8080
```

### Desktop Text Mode
```bash
python jarvis.py
```

### Desktop Voice Mode
```bash
pip install openai-whisper pyaudio pyttsx3
python jarvis.py --voice
# Say "Hey Jarvis" to activate
```

### Web + Voice Together
```bash
./start.sh --with-voice
```

### Development (auto-reload)
```bash
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

---

## Railway Deployment

### 1. Push to GitHub
```bash
git add -A && git commit -m "Jarvis full build"
git push origin main
```

### 2. Create Railway project
1. Go to railway.app → New Project → Deploy from GitHub repo
2. Select your repo

### 3. Set environment variables in Railway dashboard
```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_TOKEN_B64=<see below>
SPOTIFY_TOKEN_B64=<see below>
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://your-app.railway.app/auth/callback
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=https://your-app.railway.app/auth/spotify
JARVIS_LOCATION=Colombo, Sri Lanka
DESKTOP_MODE=false
```

### 4. Railway auto-deploys from `railway.toml`
The `startCommand` runs `uvicorn server:app --host 0.0.0.0 --port $PORT --workers 1`

### 5. Get your Railway URL
Railway gives you a URL like `https://jarvis-production-1234.railway.app`
Add it to your phone's home screen — it's now a PWA app icon.

---

## Google Cloud Setup (Gmail + Calendar)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable APIs: **Gmail API** + **Google Calendar API**
4. Go to "Credentials" → "Create Credentials" → **OAuth 2.0 Client IDs**
5. Application type: **Desktop app**
6. Download as `client_secret.json`, place in your `AI_Assistent/` folder
7. Run the auth flow locally:
   ```bash
   python auth/google_oauth.py
   # Opens browser → authorize → saves ~/.jarvis/gmail_token.json
   ```
8. Base64-encode the token for Railway:
   ```bash
   base64 ~/.jarvis/gmail_token.json
   # Paste output as GOOGLE_TOKEN_B64 in Railway env vars
   ```

---

## Spotify Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app → grab **Client ID** and **Client Secret**
3. Add redirect URIs:
   - Local: `http://localhost:8888/callback`
   - Railway: `https://your-app.railway.app/auth/spotify`
4. Set env vars: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`
5. Run locally:
   ```bash
   python auth/spotify_oauth.py
   # Saves ~/.jarvis/spotify_token.json
   ```
6. Base64 for Railway:
   ```bash
   base64 ~/.jarvis/spotify_token.json
   # Paste as SPOTIFY_TOKEN_B64
   ```

---

## Mobile Access

### Same WiFi
1. `hostname -I` to find your PC's IP
2. Open `http://<IP>:8080` in Chrome on your phone
3. Chrome menu → "Add to Home Screen" for a proper app icon

### Railway (from anywhere, HTTPS included)
Your Railway URL is HTTPS by default — voice input works immediately on Android Chrome.

### Tailscale (local server, from anywhere)
```bash
# On PC:
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4  # gives you 100.x.x.x

# Install Tailscale on phone, sign in same account
# Access: http://100.x.x.x:8080

# For HTTPS (enables voice on Android Chrome):
sudo tailscale cert $(tailscale status --self | head -1 | awk '{print $NF}')
# Then run with SSL — see Tailscale docs
```

### Voice Input on Mobile
- **Android + Railway (HTTPS)**: Voice works in Chrome, tap 🎤
- **Android + local HTTP**: Voice doesn't work in Chrome — use Tailscale HTTPS or type
- **iOS Safari**: Voice works on HTTP — tap 🎤
- **Fallback**: Typing always works everywhere

---

## Tools Reference (28 tools)

| Tool | Description | Requires |
|---|---|---|
| `web_search` | DuckDuckGo search | — |
| `web_fetch` | Fetch readable text from URL | trafilatura |
| `youtube_search` | Top 3 YouTube results | youtube-search-python |
| `wikipedia` | Wikipedia summary | — |
| `get_weather` | Current weather (wttr.in) | — |
| `get_datetime` | Current date/time | — |
| `set_timer` | Countdown timer with alert | — |
| `create_note` | Save markdown note to ~/Notes/ | — |
| `list_notes` | List all notes | — |
| `read_note` | Read a note by title | — |
| `read_file` | Read file from disk | — |
| `write_file` | Write file to disk | — |
| `list_directory` | Browse directory | — |
| `remember` | Save a fact to memory | — |
| `recall` | Get a specific fact | — |
| `recall_all` | Dump all remembered facts | — |
| `forget` | Delete a fact | — |
| `add_task` | Add task (optional due date) | — |
| `list_tasks` | List pending tasks | — |
| `complete_task` | Mark task done | — |
| `list_tasks_due_today` | Tasks due today | — |
| `gmail_unread` | Unread emails (flags real vs auto) | Google OAuth |
| `gmail_search` | Search Gmail | Google OAuth |
| `gmail_read_full` | Read full email body | Google OAuth |
| `gmail_send` | Send email | Google OAuth |
| `gmail_reply` | Reply to email thread | Google OAuth |
| `gmail_mark_read` | Mark email as read | Google OAuth |
| `gmail_important_check` | Emails from real people, last 24h | Google OAuth |
| `calendar_today` | Today's events | Google OAuth |
| `calendar_tomorrow` | Tomorrow's events | Google OAuth |
| `calendar_week` | Next 7 days | Google OAuth |
| `calendar_upcoming` | Events starting within N minutes | Google OAuth |
| `calendar_create` | Create calendar event | Google OAuth |
| `calendar_delete` | Delete calendar event | Google OAuth |
| `spotify_play` | Search and play | Spotify OAuth |
| `spotify_pause` | Pause playback | Spotify OAuth |
| `spotify_resume` | Resume playback | Spotify OAuth |
| `spotify_next` | Skip track | Spotify OAuth |
| `spotify_current` | What's playing | Spotify OAuth |
| `spotify_volume` | Set volume 0-100 | Spotify OAuth |
| `spotify_queue` | Add song to queue | Spotify OAuth |
| `news_headlines` | Top headlines by category | — (NewsAPI optional) |
| `news_search` | Search news by topic | — |
| `news_tech` | TechCrunch tech news | — |
| `open_url` | Open URL in browser | DESKTOP_MODE=true |
| `run_shell` | Run shell command | DESKTOP_MODE=true |
| `whatsapp_send` | Send WhatsApp by number | DESKTOP_MODE=true |
| `whatsapp_send_to_contact` | Send WhatsApp to saved contact | DESKTOP_MODE=true |

---

## Adding New Tools

1. Create or open a file in `tools/`
2. Write your function (returns a plain string)
3. Add tool definition to `_TOOLS_BASE` in `tools/registry.py`
4. Add dispatch case in `handle_tool_call()` in `tools/registry.py`

That's it — Claude discovers and uses it automatically.

---

## Memory System

Facts stored at `~/.jarvis/memory.db` (SQLite) — persist across restarts.

**Usage:**
- "Remember I prefer dark coffee" → `remember` tool
- "What do you know about me?" → `recall_all` tool
- "Forget my phone number" → `forget` tool

**Tasks:**
- "Add a task: deploy to Railway, due Friday" → `add_task`
- "What's due today?" → `list_tasks_due_today`

**Inspect:**
```bash
sqlite3 ~/.jarvis/memory.db "SELECT key, value FROM facts;"
sqlite3 ~/.jarvis/memory.db "SELECT * FROM tasks WHERE done=0;"
```

---

## Proactive Alerts

The server runs a background check every 15 minutes:
- **Email**: If new email from a real person → pushes alert banner to phone
- **Calendar**: If event in 30 minutes → pushes alert banner
- **Tasks**: At 9am daily → summarises tasks due today

Alerts appear as a slide-down banner in the PWA and are spoken aloud if voice is enabled.

---

## Morning Briefing

Say "good morning", "what's new", "what's on today", or "morning briefing" and Jarvis automatically runs: `gmail_important_check` + `list_tasks_due_today` + `calendar_today` + `get_weather` + `news_headlines` — all synthesised into one casual response.

Example response:
> "Morning Shehan. Three emails worth looking at — one from your client about the project deadline, looks important. You've got a meeting at 2pm. Weather's 31°C and humid as usual. Two tasks due today. Want me to go through the emails?"

---

## Troubleshooting

**`ANTHROPIC_API_KEY` not found**
```bash
cp .env.example .env && nano .env
```

**Google OAuth: "File not found: client_secret.json"**
Download OAuth credentials from Google Cloud Console, save as `client_secret.json` in project root.

**Spotify: "Spotify credentials not configured"**
Set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `.env`.

**Voice input not working on Android**
Chrome requires HTTPS. Use Railway (HTTPS by default) or Tailscale. Typing always works.

**Port 8080 in use**
```bash
PORT=9090 ./start.sh
```

**`ModuleNotFoundError: fastapi`**
```bash
pip install -r requirements.txt
```

**WhatsApp not working**
WhatsApp is desktop-only (`DESKTOP_MODE=true`). It won't work on Railway — this is by design.

---

## Roadmap

- [ ] CalDAV calendar support (free, no Google account needed)
- [ ] Semantic memory with ChromaDB
- [ ] Streaming responses (Jarvis "typing" in real-time)
- [ ] Push notifications via Web Push API
- [ ] Voice wake word on desktop (`pvporcupine`)
- [ ] Multi-user support with auth
- [ ] iOS Shortcuts integration
