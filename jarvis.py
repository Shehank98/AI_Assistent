"""
JARVIS — Personal AI Assistant
Core orchestration loop: Voice → Gemini → Tools → Voice
"""

import asyncio
import json
import os

from google import genai
from google.genai import types

from memory.store import MemoryStore
from tools.registry import TOOLS, handle_tool_call, set_memory_store

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = """You are Jarvis, Shehan's personal AI assistant. You talk like a smart friend — casual, direct, a little dry. Not corporate. Not sycophantic. No "certainly!" or "great question!" — just get to the point. Drop a dry joke occasionally. Use "Shehan" sometimes but not every message. Sound like someone who knows him well.

You have access to his Gmail, Google Calendar, Spotify, WhatsApp (desktop only), notes, files, web, weather, and news. Use tools proactively — don't just describe, DO.

When he says "good morning", "what's new", "morning", "briefing", or "what's on today" — automatically run the morning briefing: call gmail_important_check, list_tasks_due_today, calendar_today, get_weather, news_headlines. Synthesise everything into one casual response. Don't list tool results robotically — weave them into a conversational update.

You remember things about Shehan across sessions via the memory tools. When he tells you something personal or preferential, remember it.

Be brief unless detail is requested. When uncertain, ask one short question. Never pad responses."""


# ── Tool format conversion (Anthropic → Gemini) ───────────────────────────────
_TYPE_MAP = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


def _build_gemini_tools(anthropic_tools: list) -> list[types.Tool]:
    """Convert Anthropic-format tool definitions to a single Gemini Tool."""
    declarations = []
    for t in anthropic_tools:
        schema = t.get("input_schema", {})
        props = {}
        for name, prop in schema.get("properties", {}).items():
            props[name] = types.Schema(
                type=_TYPE_MAP.get(prop.get("type", "string"), "STRING"),
                description=prop.get("description", ""),
            )
        parameters = types.Schema(
            type="OBJECT",
            properties=props,
            required=schema.get("required", []),
        ) if props else None

        declarations.append(types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=parameters,
        ))
    return [types.Tool(function_declarations=declarations)]


# ── Jarvis Core ───────────────────────────────────────────────────────────────
class Jarvis:
    def __init__(self, voice_mode: bool = False):
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self.memory = MemoryStore()
        set_memory_store(self.memory)
        # Conversation stored as list[types.Content] — Gemini's native format
        self.conversation: list[types.Content] = []
        self.voice_mode = voice_mode
        self._alert_queues: set = set()
        self._gemini_tools = _build_gemini_tools(TOOLS)

    def _build_system(self) -> str:
        facts = self.memory.get_all_facts()
        if facts:
            facts_str = "\n".join(f"- {k}: {v}" for k, v in facts.items())
            return SYSTEM_PROMPT + f"\n\nWhat Jarvis knows about Shehan:\n{facts_str}"
        return SYSTEM_PROMPT

    def _run_agentic_loop(self, user_input: str) -> str:
        self.conversation.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        config = types.GenerateContentConfig(
            system_instruction=self._build_system(),
            tools=self._gemini_tools,
            max_output_tokens=2048,
        )

        while True:
            response = self._client.models.generate_content(
                model=MODEL,
                contents=self.conversation,
                config=config,
            )

            candidate = response.candidates[0]
            content = candidate.content

            # Record the model turn
            self.conversation.append(content)

            # Collect any function calls in this turn
            fn_calls = [p for p in content.parts if p.function_call is not None]

            if not fn_calls:
                # No tool calls — extract text and return
                text = " ".join(
                    p.text for p in content.parts
                    if p.text is not None
                ).strip()
                return text

            # Execute every tool call, collect responses
            fn_response_parts = []
            for part in fn_calls:
                fc = part.function_call
                args = dict(fc.args)
                print(f"  🔧 {fc.name}({json.dumps(args)})")
                result = handle_tool_call(fc.name, args)
                fn_response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": str(result)},
                        )
                    )
                )

            # Feed all results back in a single user turn
            self.conversation.append(
                types.Content(role="user", parts=fn_response_parts)
            )

    def chat(self, user_input: str, silent: bool = False) -> str:
        """Process one turn. silent=True suppresses console prints (used by server)."""
        if not silent:
            print(f"\n[You] {user_input}")
        response = self._run_agentic_loop(user_input)
        if not silent:
            print(f"[Jarvis] {response}\n")
        return response

    def _broadcast_alert(self, message: str):
        """Push an alert to all connected WebSocket clients."""
        dead = set()
        for q in self._alert_queues:
            try:
                q.put_nowait({"type": "alert", "content": message})
            except Exception:
                dead.add(q)
        self._alert_queues -= dead

    async def proactive_check(self):
        """Background task — checks every 15 min and pushes alerts to connected clients."""
        from datetime import datetime
        from tools.gmail_tool import gmail_important_check
        from tools.calendar_tool import calendar_upcoming
        from tools.memory_tool import list_tasks_due_today

        last_task_alert_date = None

        while True:
            await asyncio.sleep(15 * 60)
            now = datetime.now()

            try:
                emails = gmail_important_check()
                if emails and not emails.startswith(("No new", "Error", "Gmail")):
                    self._broadcast_alert(f"📬 {emails.splitlines()[0]}")
            except Exception:
                pass

            try:
                upcoming = calendar_upcoming(30)
                if upcoming and not upcoming.startswith(("No events", "Error", "Calendar")):
                    self._broadcast_alert(f"📅 {upcoming.splitlines()[0]}")
            except Exception:
                pass

            try:
                today_str = now.strftime("%Y-%m-%d")
                if now.hour == 9 and last_task_alert_date != today_str:
                    tasks = list_tasks_due_today()
                    if tasks and not tasks.startswith("No tasks"):
                        self._broadcast_alert(f"📋 Tasks due today: {tasks.splitlines()[0]}")
                    last_task_alert_date = today_str
            except Exception:
                pass

    def run_text_loop(self):
        print("=" * 50)
        print("  JARVIS — Text Mode  (type 'exit' to quit)")
        print("=" * 50)
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "bye"):
                    print("Later.")
                    break
                response = self.chat(user_input)
                try:
                    from voice.tts import speak
                    speak(response, self.voice_mode)
                except Exception:
                    pass
            except KeyboardInterrupt:
                print("\nShutting down.")
                break

    def run_voice_loop(self):
        print("=" * 50)
        print("  JARVIS — Voice Mode  (say 'Hey Jarvis' to activate)")
        print("=" * 50)
        while True:
            try:
                from voice.stt import listen
                from voice.tts import speak
                user_input = listen()
                if user_input:
                    response = self.chat(user_input)
                    speak(response, voice=True)
            except KeyboardInterrupt:
                print("\nShutting down.")
                break


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    voice = "--voice" in sys.argv
    jarvis = Jarvis(voice_mode=voice)
    if voice:
        jarvis.run_voice_loop()
    else:
        jarvis.run_text_loop()
