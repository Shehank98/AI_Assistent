# JARVIS — Personal AI Assistant
# Built on Claude claude-sonnet-4-5 + tool use

## Quick Start

```bash
# 1. Clone / copy this folder
cd jarvis

# 2. Install core dep
pip install anthropic

# 3. Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Run in text mode
python jarvis.py

# 5. When ready for voice:
pip install openai-whisper pyaudio pyttsx3
python jarvis.py --voice
```

## Project Structure

```
jarvis/
├── jarvis.py          # Main orchestrator — start here
├── tools/
│   └── registry.py   # All tools Claude can use (add yours here)
├── memory/
│   └── store.py      # SQLite-backed long-term memory
├── voice/
│   ├── stt.py        # Speech → text (Whisper)
│   └── tts.py        # Text → speech (ElevenLabs / Coqui / pyttsx3)
└── requirements.txt
```

## Adding a New Tool

1. Add the tool definition to `TOOLS` list in `tools/registry.py`
2. Implement the `_your_tool()` function 
3. Add it to `TOOL_MAP` dispatcher

Example — Spotify tool:
```python
# In TOOLS list:
{
    "name": "play_spotify",
    "description": "Play a song or playlist on Spotify",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Song or artist name"}
        },
        "required": ["query"]
    }
}

# Implementation:
def _play_spotify(query: str) -> str:
    import spotipy
    # ... your Spotipy code here
    return f"Playing {query}"

# In TOOL_MAP:
"play_spotify": lambda inp: _play_spotify(inp["query"]),
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ Yes | Your Claude API key |
| `ELEVENLABS_API_KEY` | Optional | For realistic voice output |
| `ELEVENLABS_VOICE_ID` | Optional | Defaults to "Rachel" voice |

## Build Order (recommended)

- [x] Phase 1: Text loop + Claude API working
- [ ] Phase 2: Add tools one by one (start with `get_weather`, `web_search`)
- [ ] Phase 3: Add Whisper STT (`pip install openai-whisper pyaudio`)
- [ ] Phase 4: Add TTS (`pip install pyttsx3` or ElevenLabs)
- [ ] Phase 5: Add ChromaDB for semantic memory
- [ ] Phase 6: Wake word with Porcupine
