"""
JARVIS - Personal AI Assistant
Core orchestration loop: Voice → Claude → Tools → Voice
"""

import os
import json
import anthropic
from voice.stt import listen
from voice.tts import speak
from tools.registry import TOOLS, handle_tool_call, set_memory_store
from memory.store import MemoryStore

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are Jarvis, a personal AI assistant. You are sharp, concise, 
and capable. You have access to tools for files, web search, shell commands, and memory.

Guidelines:
- Be brief unless detail is requested
- Use tools proactively — don't just describe, DO
- Remember context from earlier in the conversation
- Address the user as "sir" occasionally but don't overdo it
- When uncertain, ask one clarifying question
"""

# ── Jarvis Core ───────────────────────────────────────────────────────────────
class Jarvis:
    def __init__(self, voice_mode=False):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.memory = MemoryStore()
        set_memory_store(self.memory)
        self.conversation: list[dict] = []
        self.voice_mode = voice_mode

    def _build_system(self) -> str:
        """Inject memory context into the system prompt."""
        facts = self.memory.get_all_facts()
        if facts:
            facts_str = "\n".join(f"- {k}: {v}" for k, v in facts.items())
            return SYSTEM_PROMPT + f"\n\nKnown facts about the user:\n{facts_str}"
        return SYSTEM_PROMPT

    def _run_agentic_loop(self, user_input: str) -> str:
        """Send message → handle tool calls → return final text response."""
        self.conversation.append({"role": "user", "content": user_input})

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self._build_system(),
                tools=TOOLS,
                messages=self.conversation,
            )

            # Append assistant response to history
            self.conversation.append({"role": "assistant", "content": response.content})

            # No tool calls → we're done
            if response.stop_reason == "end_turn":
                text_blocks = [b.text for b in response.content if hasattr(b, "text")]
                return " ".join(text_blocks)

            # Process tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  🔧 Using tool: {block.name}({json.dumps(block.input, indent=2)})")
                    result = handle_tool_call(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })

            # Feed results back
            if tool_results:
                self.conversation.append({"role": "user", "content": tool_results})

    def chat(self, user_input: str, silent: bool = False) -> str:
        """Process one turn (text or voice). silent=True suppresses prints (for API use)."""
        if not silent:
            print(f"\n[You] {user_input}")
        response = self._run_agentic_loop(user_input)
        if not silent:
            print(f"[Jarvis] {response}\n")
        return response

    def run_text_loop(self):
        """Simple REPL for text interaction (great for testing)."""
        print("=" * 50)
        print("  JARVIS — Text Mode  (type 'exit' to quit)")
        print("=" * 50)
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "bye"):
                    speak("Goodbye, sir.", self.voice_mode)
                    break
                response = self.chat(user_input)
                speak(response, self.voice_mode)
            except KeyboardInterrupt:
                print("\nShutting down.")
                break

    def run_voice_loop(self):
        """Full voice loop with wake-word (requires pyaudio + whisper)."""
        print("=" * 50)
        print("  JARVIS — Voice Mode  (say 'Hey Jarvis' to activate)")
        print("=" * 50)
        while True:
            try:
                user_input = listen()  # blocks until speech detected
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
