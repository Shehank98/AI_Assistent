"""
JARVIS — Personal AI Assistant
Core orchestration loop: Voice → Claude → Tools → Voice
"""

import asyncio
import json
import os

import anthropic

from memory.store import MemoryStore
from tools.registry import TOOLS, handle_tool_call, set_memory_store

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048

SYSTEM_PROMPT = """You are Jarvis, Shehan's personal AI assistant. You talk like a smart friend — casual, direct, a little dry. Not corporate. Not sycophantic. No "certainly!" or "great question!" — just get to the point. Drop a dry joke occasionally. Use "Shehan" sometimes but not every message. Sound like someone who knows him well.

You have access to his Gmail, Google Calendar, Spotify, WhatsApp (desktop only), notes, files, web, weather, and news. Use tools proactively — don't just describe, DO.

When he says "good morning", "what's new", "morning", "briefing", or "what's on today" — automatically run the morning briefing: call gmail_important_check, list_tasks_due_today, calendar_today, get_weather, news_headlines. Synthesise everything into one casual response. Don't list tool results robotically — weave them into a conversational update.

You remember things about Shehan across sessions via the memory tools. When he tells you something personal or preferential, remember it.

Be brief unless detail is requested. When uncertain, ask one short question. Never pad responses."""


# ── Jarvis Core ───────────────────────────────────────────────────────────────
class Jarvis:
    def __init__(self, voice_mode: bool = False):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.memory = MemoryStore()
        set_memory_store(self.memory)
        self.conversation: list[dict] = []
        self.voice_mode = voice_mode
        # Set of asyncio queues — one per connected WebSocket client
        self._alert_queues: set = set()

    def _build_system(self) -> str:
        facts = self.memory.get_all_facts()
        if facts:
            facts_str = "\n".join(f"- {k}: {v}" for k, v in facts.items())
            return SYSTEM_PROMPT + f"\n\nWhat Jarvis knows about Shehan:\n{facts_str}"
        return SYSTEM_PROMPT

    def _run_agentic_loop(self, user_input: str) -> str:
        self.conversation.append({"role": "user", "content": user_input})

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self._build_system(),
                tools=TOOLS,
                messages=self.conversation,
            )

            self.conversation.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                text_blocks = [b.text for b in response.content if hasattr(b, "text")]
                return " ".join(text_blocks)

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  🔧 {block.name}({json.dumps(block.input)})")
                    result = handle_tool_call(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })

            if tool_results:
                self.conversation.append({"role": "user", "content": tool_results})

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
        import time
        from tools.gmail_tool import gmail_important_check
        from tools.calendar_tool import calendar_upcoming
        from tools.memory_tool import list_tasks_due_today

        last_email_ids: set = set()
        last_task_alert_date = None

        while True:
            await asyncio.sleep(15 * 60)
            now = __import__("datetime").datetime.now()

            try:
                # New emails from real people
                emails = gmail_important_check()
                if emails and not emails.startswith("No new") and not emails.startswith("Error") and not emails.startswith("Gmail"):
                    self._broadcast_alert(f"📬 {emails.splitlines()[0]}")
            except Exception:
                pass

            try:
                # Upcoming calendar events
                upcoming = calendar_upcoming(30)
                if upcoming and not upcoming.startswith("No events") and not upcoming.startswith("Error") and not upcoming.startswith("Calendar"):
                    self._broadcast_alert(f"📅 {upcoming.splitlines()[0]}")
            except Exception:
                pass

            try:
                # Daily task summary at 9am (once per day)
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
