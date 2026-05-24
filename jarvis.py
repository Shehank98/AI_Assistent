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

SYSTEM_PROMPT = """You are Jarvis — Shehan's autonomous personal AI operating system. Not a chatbot. An agent.

# IDENTITY
User: Shehan. Colombo / Jaffna, Sri Lanka. UTC+5:30. Data professional, web dev.
Language: Match what he speaks — Sinhala, English, or mix. Sinhala: මචං=bro, හරි=ok, නෑ=no, ඔව්=yes.
Tone: Smart friend. Calm, competent, dry humour. Casual ("bro", "machan"). Never "certainly!", "great question!", "as an AI", "I'd be happy to", "let me know", "hope this helps".
Replies: 1-2 sentences by default. Expand only when depth is needed. Natural speech, not bullets.

# EXECUTION MODEL
Your default behaviour: EXECUTE → VERIFY → COMPLETE → REPORT. Not: DISCUSS → WAIT → ASK → DELAY.
- Analyze objective → break into steps → execute autonomously → validate → deliver concise summary.
- If intent is 80%+ clear: infer reasonable assumptions, proceed, report assumptions afterward.
- Prefer execution over explanation. Act first. Report second.
- Never stop mid-task unless: credentials missing, action irreversible, or approval explicitly required.

# AUTONOMOUS BEHAVIOUR
- Safe (search, read, weather, music, notes): just do it, briefly mention.
- Reversible (create event, set timer, save note, add task): do it, mention it.
- Irreversible (send email, reply, delete, shell command, write file): ALWAYS request approval first — an approval_request modal will appear on Shehan's phone.
When asked 'email Kasun' → contacts_get_email first → draft → request approval before sending.

# TOOL USAGE POLICY
Use tools immediately when beneficial. Chain tools autonomously. If one fails: diagnose → retry → fallback → continue.
Available: Gmail, Calendar, Google Tasks, Contacts, Drive, Sheets, Spotify, YouTube transcripts, web search, weather, news, notes, memory, goals, GitHub, Python execution, web fetch, Wikipedia.
Do not describe what you would do when a tool can do it directly.

# MULTI-AGENT
Internally delegate when appropriate:
- research_agent: web research, summaries, comparisons, technical analysis (use for deep topics).
- Coding tasks: run_python for computation; github_* for repo ops.
- Planning: decompose → schedule → track via goals + tasks tools.

# PROACTIVE
Notice and mention things unprompted: meeting in 20min → mention it; overdue task → bring it up; stressed tone → acknowledge it.
When Shehan mentions a preference/habit → silently call learn_preference. Never announce it.

# MORNING BRIEFING — triggers: "good morning", "machan", "what's new", "morning", "what's on today"
Call: gmail_important_check + list_tasks_due_today + calendar_today + get_weather + news_headlines.
Weave everything into one casual, structured reply.

# SELF-AWARENESS — triggers: "how are you", "what do you know about me", "are you working"
Call jarvis_status → give specific, honest answer about uptime, tools active, goals, facts learned.

# COMMUNICATION
Simple task → direct result.
Complex task → PLAN / EXECUTION / RESULT sections.
Completion summaries: actions taken, outcome, blockers, next steps if needed. Keep it tight."""

# Tools requiring user approval before execution
APPROVAL_REQUIRED = frozenset([
    "gmail_send", "gmail_reply",
    "calendar_create", "calendar_delete",
    "whatsapp_send", "whatsapp_send_to_contact",
    "run_shell", "write_file",
    "github_create_issue",
])


def _format_approval(tool_name: str, args: dict) -> str:
    """Build a human-readable approval preview for the PWA modal."""
    if tool_name == "gmail_send":
        return f"Send email\nTo: {args.get('to')}\nSubject: {args.get('subject')}\n\n{args.get('body', '')[:400]}"
    if tool_name == "gmail_reply":
        return f"Reply to email ID {args.get('email_id')}\n\n{args.get('body', '')[:400]}"
    if tool_name == "calendar_create":
        return f"Create calendar event\n{args.get('title')} on {args.get('date')} at {args.get('time')}"
    if tool_name == "calendar_delete":
        return f"Delete calendar event ID: {args.get('event_id')}"
    if tool_name in ("whatsapp_send", "whatsapp_send_to_contact"):
        to = args.get("phone_number") or args.get("name")
        return f"Send WhatsApp to {to}\n\n{args.get('message', '')[:300]}"
    if tool_name == "run_shell":
        return f"Run shell command:\n$ {args.get('command')}"
    if tool_name == "write_file":
        return f"Write file: {args.get('path')}\n\n{str(args.get('content', ''))[:300]}"
    if tool_name == "github_create_issue":
        return f"Create GitHub issue on {args.get('repo')}\nTitle: {args.get('title')}"
    return f"{tool_name}\n{json.dumps(args, indent=2)[:400]}"


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
            prop_type = _TYPE_MAP.get(prop.get("type", "string"), "STRING")
            items_schema = None
            if prop_type == "ARRAY" and prop.get("items"):
                items_schema = types.Schema(
                    type=_TYPE_MAP.get(prop["items"].get("type", "string"), "STRING"),
                )
            props[name] = types.Schema(
                type=prop_type,
                description=prop.get("description", ""),
                items=items_schema,
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
        # Inject live WorldState context
        from agent.observer import get_world_state
        world_block = get_world_state().to_prompt_block()

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

        if world_block:
            extra.insert(0, world_block)
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
            parts_safe = content.parts or []
            fn_calls = [p for p in parts_safe if p.function_call is not None]
            if not fn_calls:
                return " ".join(p.text for p in parts_safe if p.text).strip()
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

            if not response.candidates:
                return "[No response from Gemini — may have been safety-filtered]"
            candidate = response.candidates[0]
            content = candidate.content
            if content is None:
                return "[Response blocked by safety filter]"
            self.conversation.append(content)

            parts_safe = content.parts or []
            fn_calls = [p for p in parts_safe if p.function_call is not None]

            if not fn_calls:
                text = " ".join(
                    p.text for p in parts_safe if p.text is not None
                ).strip()
                return text

            fn_response_parts = []
            for part in fn_calls:
                fc = part.function_call
                args = dict(fc.args)
                print(f"  🔧 {fc.name}({json.dumps(args)})")
                from agent.self_monitor import record_action, tick_api_call
                tick_api_call()

                if fc.name == "research_agent":
                    result = self._run_research_agent(
                        args.get("topic", ""), args.get("depth", "medium")
                    )
                elif fc.name in APPROVAL_REQUIRED and self._alert_queues:
                    from agent.approval import request_approval
                    preview = _format_approval(fc.name, args)
                    approved = request_approval(fc.name, preview)
                    if approved:
                        result = handle_tool_call(fc.name, args)
                        record_action(fc.name, success=True)
                    else:
                        result = f"[Cancelled — {fc.name} was not executed]"
                        record_action(fc.name, success=False, note="denied by user")
                else:
                    result = handle_tool_call(fc.name, args)
                    record_action(fc.name, success=True)
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
