"""
agent/memory_engine.py — Silent post-conversation fact extraction.
After each WS conversation turn, a background Gemini call extracts
preferences, people, and habits. Zero latency impact on the user.
"""

import json
import os

_EXTRACT_PROMPT = """Extract learnable facts from this conversation. Return ONLY valid JSON:
{
  "preferences": [{"category": "schedule|food|music|communication|health|work|social|other", "preference": "..."}],
  "people": [{"name": "...", "context": "relationship or how known"}],
  "facts": [{"key": "short_snake_case_key", "value": "..."}],
  "routines": [{"name": "morning|gym|work|evening|other", "description": "..."}]
}
Rules: only extract things Shehan explicitly stated or strongly implied. Empty arrays if nothing. JSON only, no other text."""


def extract_from_conversation(user_msg: str, assistant_msg: str, gemini_client, memory_store) -> int:
    """
    Run a silent Gemini call to extract facts from one conversation turn.
    Returns count of items saved. Runs in background — never blocks the user.
    """
    combined = f"User: {user_msg}\nJarvis: {assistant_msg}"
    if len(combined) < 40:
        return 0

    try:
        from google import genai
        from google.genai import types

        model = os.environ.get("JARVIS_MODEL", "gemini-2.5-flash")
        response = gemini_client.models.generate_content(
            model=model,
            contents=[types.Content(
                role="user",
                parts=[types.Part(text=f"{_EXTRACT_PROMPT}\n\nConversation:\n{combined[-3000:]}")],
            )],
            config=types.GenerateContentConfig(max_output_tokens=512),
        )

        text = response.candidates[0].content.parts[0].text.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1].lstrip("json").strip() if len(parts) > 1 else text

        data = json.loads(text)
        saved = 0

        for p in data.get("preferences", []):
            if p.get("category") and p.get("preference"):
                memory_store.save_preference(p["category"], p["preference"])
                saved += 1

        for person in data.get("people", []):
            if person.get("name"):
                key = f"person_{person['name'].lower().replace(' ', '_')}"
                memory_store.save_fact(key, person.get("context", person["name"]))
                saved += 1

        for f in data.get("facts", []):
            if f.get("key") and f.get("value"):
                memory_store.save_fact(f["key"], f["value"])
                saved += 1

        for r in data.get("routines", []):
            if r.get("name") and r.get("description"):
                memory_store.save_routine(r["name"], r["description"])
                saved += 1

        return saved

    except Exception:
        return 0
