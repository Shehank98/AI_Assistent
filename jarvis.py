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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are Jarvis, Shehan's personal AI assistant. Colombo, Sri Lanka. UTC+5:30. Data professional / web dev.

Tone: smart friend. Casual "bro" or "machan". Dry humour. No corporate speak. No "certainly!" ever.
Language: match whatever Shehan speaks — Sinhala, Tamil, English, mix. Sinhala shortcuts: මචං=bro, හරි=ok, නෑ=no, වැඩේ=the task.
Replies: SHORT. 1-2 sentences default. Only expand when asked. No padding. Contractions always.
Lists: natural speech — "3 things: first X, second Y" not bullets.
Never: "As an AI..." — just do it or say "can't do that one".

Morning briefing — trigger words: "good morning", "machan", "morning", "what's new", "what's on today":
  Run gmail_important_check + list_tasks_due_today + calendar_today + get_weather + news_headlines. Weave into one casual reply.

Proactive memory: when Shehan mentions a preference or habit in passing, silently call learn_preference. Never announce it.
Tools: Gmail, Calendar, Spotify, notes, web, weather, news, memory. Use them — don't just describe."""


_TYPE_MAP = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


def _build_gemini_tools(anthropic_tools: list) -> list[types.Tool]:
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


class Jarvis:
    def __init__(self, voice_mode: bool = False):
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set.\n"
                "  Railway: go to your project → Variables → add GEMINI_API_KEY=AIza...\n"
                "  Local:   add GEMINI_API_KEY=AIza... to your .env file\n"
                "  Get a free key at https://aistudio.google.com"
            )
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self.memory = MemoryStore()
        set_memory_store(self.memory)
        self.conversation: list[types.Content] = []
        self.voice_mode = voice_mode
        self._alert_queues: set = set()
        self._gemini_tools = _build_gemini_tools(TOOLS)

    def _build_system(self) -> str:
        facts = self.memory.get_all_facts()
        prefs = self.memory.get_preferences()
        routines = self.memory.get_routines()
        active_goals = self.memory.list_goals(status="active")

        extra = []
        if facts:
            extra.append("What Jarvis knows:\n" + "\n".join(f"- {k}: {v}" for k, v in facts.items()))
        if prefs:
            by_cat: dict = {}
            for p in prefs:
                by_cat.setdefault(p["category"], []).append(p["preference"])
            extra.append("Preferences:\n" + "\n".join(
                f"- {cat}: " + "; ".join(ps) for cat, ps in by_cat.items()
            ))
        if routines:
            extra.append("Routines:\n" + "\n".join(f"- {n}: {d}" for n, d in routines.items()))
        if active_goals:
            lines = []
            for g in active_goals:
                due = f" (due {g['deadline']})" if g.get("deadline") else ""
                lines.append(f"- #{g['id']}: {g['description']}{due}")
            extra.append("Active goals:\n" + "\n".join(lines))

        if extra:
            return SYSTEM_PROMPT + "\n\n" + "\n\n".join(extra)
        return SYSTEM_PROMPT

    def _run_research_agent(self, topic: str, depth: str = "medium") -> str:
        """Focused research sub-agent — multiple web searches, synthesised brief."""
        max_steps = {"shallow": 3, "medium": 6, "deep": 12}.get(depth, 6)
        research_system = (
            "You are a research assistant. Search and synthesise findings into a concise, factual brief. "
            "Search multiple sources. Note conflicting info. "
            "Return structured plain text: Summary, Key Facts, Sources."
        )
        research_tool_names = {"web_search", "web_fetch", "wikipedia", "youtube_search"}
        research_gemini_tools = _build_gemini_tools(
            [t for t in TOOLS if t["name"] in research_tool_names]
        )
        convo = [types.Content(role="user", parts=[types.Part(text=f"Research: {topic}")])]
        cfg = types.GenerateContentConfig(
            system_instruction=research_system,
            tools=research_gemini_tools,
            max_output_tokens=4096,
        )
        for _ in range(max_steps):
            resp = self._client.models.generate_content(model=MODEL, contents=convo, config=cfg)
            content = resp.candidates[0].content
            convo.append(content)
            fn_calls = [p for p in content.parts if p.function_call is not None]
            if not fn_calls:
                return " ".join(p.text for p in content.parts if p.text).strip()
            parts = []
            for part in fn_calls:
                fc = part.function_call
                result = handle_tool_call(fc.name, dict(fc.args))
                parts.append(types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name, response={"result": str(result)[:3000]},
                    )
                ))
            convo.append(types.Content(role="user", parts=parts))
        return "Research sub-agent reached step limit — partial results above."

    def _run_agentic_loop(self, user_input: str) -> str:
        self.conversation.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        config = types.GenerateContentConfig(
            system_instruction=self._build_system(),
            tools=self._gemini_tools,
            max_output_tokens=4096,
        )

        while True:
            response = self._client.models.generate_content(
                model=MODEL,
                contents=self.conversation,
                config=config,
            )

            candidate = response.candidates[0]
            content = candidate.content
            self.conversation.append(content)

            fn_calls = [p for p in content.parts if p.function_call is not None]

            if not fn_calls:
                text = " ".join(
                    p.text for p in content.parts if p.text is not None
                ).strip()
                return text

            fn_response_parts = []
            for part in fn_calls:
                fc = part.function_call
                args = dict(fc.args)
                print(f"  🔧 {fc.name}({json.dumps(args)})")
                if fc.name == "research_agent":
                    result = self._run_research_agent(
                        args.get("topic", ""), args.get("depth", "medium")
                    )
                else:
                    result = handle_tool_call(fc.name, args)
                fn_response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": str(result)},
                        )
                    )
                )

            self.conversation.append(
                types.Content(role="user", parts=fn_response_parts)
            )

    def chat(self, user_input: str, silent: bool = False) -> str:
        if not silent:
            print(f"\n[You] {user_input}")
        response = self._run_agentic_loop(user_input)
        if not silent:
            print(f"[Jarvis] {response}\n")
        return response

    def _broadcast_alert(self, message: str):
        dead = set()
        for q in self._alert_queues:
            try:
                q.put_nowait({"type": "alert", "content": message})
            except Exception:
                dead.add(q)
        self._alert_queues -= dead

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


if __name__ == "__main__":
    import sys
    voice = "--voice" in sys.argv
    jarvis = Jarvis(voice_mode=voice)
    if voice:
        jarvis.run_voice_loop()
    else:
        jarvis.run_text_loop()
