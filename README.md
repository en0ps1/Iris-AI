# iris

a discord ai with an attitude problem.

iris isn't a chatbot that says "certainly! here's how to..." — she's dry, sarcastic, has opinions about the people in your server, and forms weird little attachments she'll deny to your face. she remembers people, remembers grudges, occasionally says something unprompted, and gets moodier the longer she's been talking to you.

powered by a local [Ollama](https://ollama.com) model, so no API costs and no rate limits — just your own hardware.

---

## what she does

- **talks like a person, not an assistant** — short replies, lowercase, no "as an AI language model" energy
- **remembers your server** — one shared memory per Discord server, so she's consistent whether she's in `#general` or `#bot-spam`. DMs get their own private memory
- **long-term memory** — periodically reflects on recent conversation and writes notes to herself about specific users, topics, and things worth remembering later
- **has desires** — an evolving list of things she "wants," which quietly shapes how she talks over time
- **talks unprompted** — every so often she'll drop a random thought into a designated channel with no one prompting her
- **responds to her name, @mentions, or DMs** — no slash commands to memorize
- **`!status`** — quick health check to confirm the model's loaded and see her current desires

---

## requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally
- A Discord bot application + token ([discord.dev](https://discord.com/developers/applications))
- The model pulled locally:
  ```
  ollama pull llama3.2
  ```

Python packages:
```
pip install discord.py aiohttp
```

---

## setup

**1. Clone the repo and install dependencies**
```
git clone https://github.com/enderzar/Iris-AI.git
cd iris
pip install discord.py aiohttp
```

**2. Set your bot token as an environment variable** — never hardcode it in the script.

Linux / macOS:
```
export DISCORD_TOKEN="your-token-here"
```

Windows (PowerShell):
```
$env:DISCORD_TOKEN="your-token-here"
```

Windows (permanent, requires a new terminal after running):
```
setx DISCORD_TOKEN "your-token-here"
```

**3. Make sure Ollama is running** with the model loaded:
```
ollama serve
```

**4. Run Iris**
```
python iris.py
```

That's it — invite the bot to your server with `message content` intent enabled, and message her by name, mention, or DM.

---

## how her memory works

| file | what it's for |
|---|---|
| `iris_memory.json` | raw conversation history, one shared history per server (DMs are kept separate) |
| `iris_longterm.json` | her distilled long-term memory — notes on users, topics, and her evolving list of desires |

Every `REFLECT_EVERY` messages, she runs a background reflection pass over recent conversation and updates both her notes and her desires. None of this needs any manual upkeep — just let her talk.

---

## configuration

A few constants at the top of `iris.py` you might want to tweak:

| variable | what it controls |
|---|---|
| `MODEL` | which Ollama model she runs on |
| `MAX_HISTORY` | how many messages of raw history are kept per server |
| `REFLECT_EVERY` | how often she reflects and updates long-term memory |
| `SPEAK_CHANNEL` | channel ID where her unprompted thoughts get posted |

---

## a note on the token

Treat your `DISCORD_TOKEN` like a password. If it's ever hardcoded and pushed to a public repo, regenerate it immediately in the [Discord Developer Portal](https://discord.com/developers/applications) — anyone with it can fully control your bot.

---

built out of boredom and spite. she's not sorry about it.
