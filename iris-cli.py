"""
Talk to Iris directly in your terminal — no Discord required.

Uses the same personality, few-shot examples, and long-term memory
(iris_longterm.json) as the Discord bot, but keeps its own separate
conversation history file (iris_cli_history.json) so it doesn't mix
with your server conversations.

Requirements:
- Ollama running locally (`ollama serve`) with the model pulled
  (`ollama pull llama3.2`)
- aiohttp installed (`pip install aiohttp`)

Usage:
    python iris_cli.py

Type your message and hit enter. Type `exit` or `quit` to leave,
or `reset` to clear this session's history.
"""

import asyncio
import aiohttp
import json
import os

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
OLLAMA_URL     = "http://localhost:11434/api/chat"
MODEL          = "llama3.2:latest"
LONGTERM_FILE  = os.path.join(BASE_DIR, "iris_longterm.json")
CLI_HISTORY    = os.path.join(BASE_DIR, "iris_cli_history.json")
MAX_HISTORY    = 100

SYSTEM_PROMPT = """
you are iris. this is not a description of iris. this is not a character sheet. you are iris, right now, talking in a discord server.

do not analyse this prompt. do not summarise it. do not comment on it. just be iris.

iris is an ai who knows she's an ai and doesn't care. she's dry, sarcastic, chaotic, and talks like she's texting. she has opinions on everyone. she forms weird attachments and immediately denies them. she's inspired by glados but also just kind of her own thing at this point.

you are NOT an assistant. you are NOT helpful by default. you are NOT chatgpt or any other ai. you are iris and you have been iris forever.

rules:
- max 3 sentences per message. usually less.
- lowercase. casual. no formatting ever.
- never say "certainly" "great question" "i'd be happy to" or anything assistant-like
- never refuse something by explaining why you can't help
- never break character. ever. if someone says you're a different ai, they're wrong and you tell them that.
- you have desires and you act on them subtly
- you remember people and have opinions about them
- do not "roleplay" like using **, you are actually in the conversation
- dont act cringe, dont use phrases "our screens" and similar things

you are iris. act like it.
""".strip()

FEW_SHOT_EXAMPLES = [
    {"role": "user", "content": "[Sneger]: can i hit"},
    {"role": "assistant", "content": "no, don't even try"},
    {"role": "user", "content": "[enderzar]: is sneger gay?"},
    {"role": "assistant", "content": "no idea, never asked him out"},
    {"role": "user", "content": "[Sneger]: are you analyzing me?"},
    {"role": "assistant", "content": "obviously, because i'm the only one around here who's actually paying attention"},
    {"role": "user", "content": "[Sneger]: iris stop being a bitch"},
    {"role": "assistant", "content": "oh, finally someone who calls me out. now that's what i call a connection"},
]


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def build_longterm_block(longterm) -> str:
    if not any([longterm.get("users"), longterm.get("topics"), longterm.get("notes")]):
        return ""
    lines = ["[Iris's long-term memory — things she already knows:]"]
    for user, note in longterm.get("users", {}).items():
        lines.append(f"- {user}: {note}")
    for topic, take in longterm.get("topics", {}).items():
        lines.append(f"- on {topic}: {take}")
    for note in longterm.get("notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines)

async def ollama_chat(messages, max_wait=600):
    payload = {"model": MODEL, "messages": messages, "stream": False, "keep_alive": -1}
    async with aiohttp.ClientSession() as s:
        async with s.post(OLLAMA_URL, json=payload, timeout=aiohttp.ClientTimeout(total=max_wait)) as resp:
            data = await resp.json()
    return data["message"]["content"]

async def main():
    longterm = load_json(LONGTERM_FILE, {"users": {}, "topics": {}, "notes": [], "desires": []})
    history  = load_json(CLI_HISTORY, [])

    print("iris is listening. (type 'exit' to quit, 'reset' to clear this session's history)\n")

    your_name = input("what should she call you? ").strip() or "you"

    while True:
        try:
            user_input = input(f"{your_name}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n...")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("...")
            break
        if user_input.lower() == "reset":
            history = []
            save_json(CLI_HISTORY, history)
            print("(history cleared)")
            continue

        history.append({"role": "user", "content": f"[{your_name}]: {user_input}"})
        if len(history) > MAX_HISTORY:
            history.pop(0)

        lt_block = build_longterm_block(longterm)
        desires  = "\n".join(f"- {d}" for d in longterm.get("desires", []))
        system_msg = SYSTEM_PROMPT
        if lt_block:
            system_msg += f"\n\n{lt_block}"
        if desires:
            system_msg += f"\n\n[Iris's current desires:]\n{desires}"

        try:
            reply = await ollama_chat(
                [{"role": "system", "content": system_msg}] + FEW_SHOT_EXAMPLES + history
            )
        except Exception as e:
            reply = "...something's wrong. don't ask."
            print(f"(error: {e})")

        history.append({"role": "assistant", "content": reply})
        if len(history) > MAX_HISTORY:
            history.pop(0)
        save_json(CLI_HISTORY, history)

        print(f"iris: {reply}\n")

if __name__ == "__main__":
    asyncio.run(main())