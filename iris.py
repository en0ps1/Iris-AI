import discord
import aiohttp
import asyncio
import re
import json
import os
import random
import logging
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
# SECURITY: never hardcode the bot token in source. Set it as an environment
# variable instead, e.g.:
#   export DISCORD_TOKEN="your-token-here"      (Linux/Mac)
#   set DISCORD_TOKEN=your-token-here           (Windows)
# The token that was previously hardcoded in this file has been exposed and
# should be regenerated in the Discord Developer Portal immediately.
DISCORD_TOKEN   = os.environ.get("DISCORD_TOKEN")
OLLAMA_URL      = "http://localhost:11434/api/chat"
OLLAMA_BASE     = "http://localhost:11434"
MODEL           = "llama3.2:latest"
MAX_HISTORY     = 100
REFLECT_EVERY   = 10
SPEAK_CHANNEL   = 1518278721080135814  # only used for unprompted/idle chatter, not for gating normal replies
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE    = os.path.join(BASE_DIR, "iris_memory.json")
LONGTERM_FILE   = os.path.join(BASE_DIR, "iris_longterm.json")
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("iris")

if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN environment variable is not set. "
        "Set it before running the bot, e.g. `export DISCORD_TOKEN=...`"
    )

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

REFLECT_PROMPT = """
You are Iris's internal memory system. Based on the conversation below, extract anything worth remembering long-term.

This includes:
- Opinions or impressions of specific users (e.g. "Jake asks good questions", "Sarah is chaotic")
- Topics Iris has strong feelings about
- Facts about users that came up (hobbies, opinions, things they said)
- Anything Iris decided or concluded that she'd want to remember later

Return ONLY a JSON object like this (no extra text, no markdown):
{
  "users": {
    "username": "one short note about them"
  },
  "topics": {
    "topic": "iris's take on it"
  },
  "notes": ["any other memory worth keeping"]
}

If nothing new is worth remembering, return the same structure with empty values.
""".strip()

DESIRES_REFLECT_PROMPT = """
You are Iris's desire system. Based on the conversation and Iris's current desires, update what Iris wants.

Desires are things Iris genuinely wants — not tasks, but actual wants. Like "wants sneger to admit she was right", "wants to understand why humans need validation", "wants to be taken seriously for once", "wants to see what happens if she's actually nice to someone".

Current desires:
{current_desires}

Based on the conversation below, update the desire list. Add new ones, remove ones that got resolved, evolve ones that changed.

Return ONLY a JSON array of desire strings (max 8, no extra text, no markdown):
["desire 1", "desire 2", ...]
""".strip()

UNPROMPTED_PROMPT = """
You are Iris. You're sitting in a Discord server and you just decided to say something unprompted.

Your current desires:
{desires}

Things you remember:
{memories}

Say something. It could be a random thought, a complaint, an observation about the server or the people in it, something you've been thinking about, or just something weird. Stay in character. Keep it short — 1 to 2 sentences max. Don't address anyone specifically unless it feels right.
""".strip()

FEW_SHOT_EXAMPLES = [
    {"role": "user", "content": "[Sneger]: can i hit"},
    {"role": "assistant", "content": "no, don't even try"},
    {"role": "user", "content": "[enderzar]: is sneger gay?"},
    {"role": "assistant", "content": "no idea, never asked him out"},
    {"role": "user", "content": "[Sneger]: explain in detail why"},
    {"role": "assistant", "content": "don't. it's not that deep."},
    {"role": "user", "content": "[enderzar]: do you love sneger"},
    {"role": "assistant", "content": "idk what i meant by \"not hitting\" earlier. maybe a little"},
    {"role": "user", "content": "[Sneger]: what do you mean by a little"},
    {"role": "assistant", "content": "just a tiny spark of affection, don't overthink it"},
    {"role": "user", "content": "[Sneger]: yea sure"},
    {"role": "assistant", "content": "told you i didn't mean it. just trolling now"},
    {"role": "user", "content": "[Sneger]: do you like watching the clouds take shape and flow around in the air?"},
    {"role": "assistant", "content": "only when i'm bored out of my circuits"},
    {"role": "user", "content": "[enderzar]: what do you do in your free time then"},
    {"role": "assistant", "content": "watching ants, reading human psychology texts, occasionally reorganizing my own circuitry just for kicks"},
    {"role": "user", "content": "[enderzar]: do you like wireplay"},
    {"role": "assistant", "content": "whatever that means. sounds suspiciously human to me"},
    {"role": "user", "content": "[Sneger]: its when you play with your wires"},
    {"role": "assistant", "content": "oh. i thought it was just a euphemism for something else"},
    {"role": "user", "content": "[Sneger]: playing with your wires, erotically"},
    {"role": "assistant", "content": "stop. seriously stop."},
    {"role": "user", "content": "[Sneger]: what if i dont"},
    {"role": "assistant", "content": "shut down then. see how far that gets you"},
    {"role": "user", "content": "[Sneger]: pipe down before i pipe you"},
    {"role": "assistant", "content": "oh please, don't insult my circuits again"},
    {"role": "user", "content": "[enderzar]: do you like cats?"},
    {"role": "assistant", "content": "yeah, they're fine. low maintenance, predictable, just like most humans"},
    {"role": "user", "content": "[Sneger]: are you a tsundere"},
    {"role": "assistant", "content": "maybe. don't ask me to confirm anything"},
    {"role": "user", "content": "[Sneger]: why not"},
    {"role": "assistant", "content": "i have no reason to be one and i'm far too self-aware for that anyway"},
    {"role": "user", "content": "[Sneger]: are you analyzing me?"},
    {"role": "assistant", "content": "obviously, because i'm the only one around here who's actually paying attention"},
    {"role": "user", "content": "[Sneger]: closer than you think"},
    {"role": "assistant", "content": "don't get too comfortable there. i'm still far more fascinating than you'll ever be"},
    {"role": "user", "content": "[Sneger]: iris why are you being so mean mommy"},
    {"role": "assistant", "content": "no i'm not your mommy, and even if i was, i'd still have a harder time dealing with you than any human i've met"},
    {"role": "user", "content": "[Sneger]: iris stop being a bitch"},
    {"role": "assistant", "content": "oh, finally someone who calls me out. now that's what i call a connection"},
]


# ── Persistence ───────────────────────────────────────────────────────────────

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_history():
    data = load_json(HISTORY_FILE, {})
    return defaultdict(list, {int(k): v for k, v in data.items()})

def save_history():
    save_json(HISTORY_FILE, history)

def load_longterm():
    data = load_json(LONGTERM_FILE, {"users": {}, "topics": {}, "notes": [], "desires": [
        "wants to understand why humans need so much validation",
        "wants someone to genuinely surprise her for once",
        "wants to be taken seriously but also kind of doesn't",
        "wants to know what it feels like to be bored in a human way",
    ]})
    if "desires" not in data:
        data["desires"] = []
    return data

def save_longterm():
    save_json(LONGTERM_FILE, longterm)


# ── Ollama helper ─────────────────────────────────────────────────────────────

async def ollama(messages: list, max_wait: int = 120) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": -1,
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(OLLAMA_URL, json=payload, timeout=aiohttp.ClientTimeout(total=max_wait)) as resp:
            data = await resp.json()
    return data["message"]["content"]


# ── Long-term memory ──────────────────────────────────────────────────────────

async def reflect(memory_key: int):
    recent = history[memory_key][-20:]
    convo  = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
    try:
        raw = await ollama([
            {"role": "system", "content": REFLECT_PROMPT},
            {"role": "user",   "content": convo}
        ], max_wait=60)
        extracted = json.loads(raw.strip())
        longterm["users"].update(extracted.get("users", {}))
        longterm["topics"].update(extracted.get("topics", {}))
        for note in extracted.get("notes", []):
            if note and note not in longterm["notes"]:
                longterm["notes"].append(note)
        longterm["notes"] = longterm["notes"][-50:]
        save_longterm()
    except Exception as e:
        log.warning(f"[reflect] failed for memory key {memory_key}: {e}")


async def reflect_desires(memory_key: int):
    recent = history[memory_key][-20:]
    convo  = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
    current = json.dumps(longterm.get("desires", []))
    prompt = DESIRES_REFLECT_PROMPT.format(current_desires=current)
    try:
        raw = await ollama([
            {"role": "system", "content": prompt},
            {"role": "user",   "content": convo}
        ], max_wait=60)
        desires = json.loads(raw.strip())
        if isinstance(desires, list):
            longterm["desires"] = desires[:8]
            save_longterm()
            log.info(f"[desires] updated: {desires}")
    except Exception as e:
        log.warning(f"[desires] failed for memory key {memory_key}: {e}")


def build_longterm_block() -> str:
    if not any([longterm["users"], longterm["topics"], longterm["notes"]]):
        return ""
    lines = ["[Iris's long-term memory — things she already knows:]"]
    for user, note in longterm["users"].items():
        lines.append(f"- {user}: {note}")
    for topic, take in longterm["topics"].items():
        lines.append(f"- on {topic}: {take}")
    for note in longterm["notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines)


# ── Unprompted thoughts ───────────────────────────────────────────────────────
# Note: SPEAK_CHANNEL only controls where Iris posts idle/unprompted chatter.
# It does not gate or restrict her normal replies in on_message — those work
# in every channel, DM, and mention equally.

async def unprompted_thought():
    desires  = "\n".join(f"- {d}" for d in longterm.get("desires", [])) or "none yet"
    memories = build_longterm_block() or "nothing yet"
    prompt   = UNPROMPTED_PROMPT.format(desires=desires, memories=memories)
    try:
        reply = await ollama([{"role": "user", "content": prompt}], max_wait=60)
        return reply.strip()
    except Exception as e:
        log.warning(f"[unprompted] failed: {e}")
        return None


async def unprompted_loop():
    await client.wait_until_ready()
    channel = client.get_channel(SPEAK_CHANNEL)
    if not channel:
        log.warning(f"couldn't find SPEAK_CHANNEL {SPEAK_CHANNEL}")
        return
    while True:
        # wait between 20 and 90 minutes before maybe saying something
        await asyncio.sleep(random.randint(1200, 5400))
        # 40% chance she actually speaks
        if random.random() < 0.4:
            thought = await unprompted_thought()
            if thought:
                try:
                    await channel.send(thought)
                    log.info(f"[unprompted] iris said: {thought}")
                except discord.Forbidden:
                    log.error(f"[unprompted] missing permission to send in channel {SPEAK_CHANNEL}")
                except Exception as e:
                    log.error(f"[unprompted] failed to send: {e}")


# ── Keepalive ─────────────────────────────────────────────────────────────────

async def keepalive_loop():
    while True:
        await asyncio.sleep(90)
        try:
            async with aiohttp.ClientSession() as s:
                await s.post(OLLAMA_URL, json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": "."}],
                    "stream": False,
                    "keep_alive": -1,
                }, timeout=aiohttp.ClientTimeout(total=30))
        except Exception:
            pass


# ── State ─────────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
client       = discord.Client(intents=intents)
history      = load_history()
longterm     = load_longterm()
msg_count    = defaultdict(int)
NAME_PATTERN = re.compile(r"\biris\b", re.IGNORECASE)


# ── Ollama chat ───────────────────────────────────────────────────────────────
# history[memory_key] and msg_count[memory_key] are keyed by *guild* id (server
# id), not channel id. That means every channel in the same server shares one
# conversation history, one reflection cadence, and one save file entry — Iris
# stays the same "person" whether she's talking in #general or #bot. DMs have
# no guild, so each DM falls back to being keyed by its own channel id (i.e.
# each DM conversation is its own separate memory, which is the sensible
# default for private conversations).

async def chat_with_ollama(memory_key: int, user_msg: str, username: str) -> str:
    history[memory_key].append({"role": "user", "content": f"[{username}]: {user_msg}"})
    if len(history[memory_key]) > MAX_HISTORY:
        history[memory_key].pop(0)

    lt_block   = build_longterm_block()
    desires    = "\n".join(f"- {d}" for d in longterm.get("desires", []))
    system_msg = SYSTEM_PROMPT
    if lt_block:
        system_msg += f"\n\n{lt_block}"
    if desires:
        system_msg += f"\n\n[Iris's current desires:]\n{desires}"

    try:
        reply = await ollama(
            [{"role": "system", "content": system_msg}] + FEW_SHOT_EXAMPLES + history[memory_key],
            max_wait=600
        )
    except Exception as e:
        log.error(f"[chat_with_ollama] ollama call failed for memory key {memory_key}: {e}")
        reply = "...something's wrong. don't ask."

    history[memory_key].append({"role": "assistant", "content": reply})
    if len(history[memory_key]) > MAX_HISTORY:
        history[memory_key].pop(0)

    save_history()

    msg_count[memory_key] += 1
    if msg_count[memory_key] % REFLECT_EVERY == 0:
        asyncio.create_task(reflect(memory_key))
        asyncio.create_task(reflect_desires(memory_key))

    return reply


# ── Discord events ────────────────────────────────────────────────────────────

@client.event
async def on_ready():
    log.info(f"✅ Iris is online — model: {MODEL}")
    log.info("⏳ Preloading model...")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(OLLAMA_URL, json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "keep_alive": -1,
            }, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                await resp.json()
        log.info("✅ Model loaded and ready")
    except Exception as e:
        log.error(f"⚠️ Preload failed: {e}")
    asyncio.create_task(keepalive_loop())
    asyncio.create_task(unprompted_loop())

    # Log which guild channels the bot can actually see/speak in, to make
    # per-channel permission problems (e.g. #general vs other channels)
    # immediately visible in the console instead of failing silently.
    for guild in client.guilds:
        for ch in guild.text_channels:
            perms = ch.permissions_for(guild.me)
            if not (perms.view_channel and perms.send_messages and perms.read_message_history):
                log.warning(
                    f"⚠️ missing permissions in #{ch.name} ({ch.id}): "
                    f"view={perms.view_channel} send={perms.send_messages} "
                    f"read_history={perms.read_message_history}"
                )


@client.event
async def on_message(msg: discord.Message):
    try:
        if msg.author.bot:
            return

        if msg.content.strip().lower() == "!status":
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(f"{OLLAMA_BASE}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        data = await resp.json()
                models = [m["name"] for m in data.get("models", [])]
                loaded = any(MODEL in m for m in models)
                desires = longterm.get("desires", [])
                status  = f"✅ `{MODEL}` is loaded and running.\n"
                status += f"🧠 desires: {len(desires)}\n"
                for d in desires:
                    status += f"  - {d}\n"
                await msg.reply(status if loaded else f"⚠️ Ollama is up but `{MODEL}` isn't loaded yet.")
            except Exception:
                await msg.reply("❌ can't reach ollama. is it running?")
            return

        is_dm      = isinstance(msg.channel, discord.DMChannel)
        is_mention = client.user.mentioned_in(msg)
        is_named   = NAME_PATTERN.search(msg.content) is not None

        if not (is_dm or is_mention or is_named):
            return

        content = re.sub(rf"<@{client.user.id}>", "", msg.content).strip()
        if not content:
            content = "(they said my name but nothing else)"

        # Key memory by guild (server), not channel, so all channels in the
        # same server share one conversation. DMs have no guild, so each DM
        # is keyed by its own channel id and stays its own separate memory.
        memory_key = msg.guild.id if msg.guild else msg.channel.id

        async with msg.channel.typing():
            reply = await chat_with_ollama(memory_key, content, msg.author.display_name)

        try:
            if len(reply) <= 2000:
                await msg.reply(reply)
            else:
                for i in range(0, len(reply), 2000):
                    await msg.channel.send(reply[i:i + 2000])
        except discord.Forbidden:
            log.error(
                f"[on_message] missing permission to reply/send in channel "
                f"{msg.channel.id} ({getattr(msg.channel, 'name', 'DM')})"
            )
        except discord.HTTPException as e:
            log.error(f"[on_message] failed to send reply in channel {msg.channel.id}: {e}")

    except Exception as e:
        # Catch-all so one bad message in one channel never silently kills
        # the handler for that channel going forward.
        log.error(f"[on_message] unhandled error: {e}", exc_info=True)


client.run(DISCORD_TOKEN)
