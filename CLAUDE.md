# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Run locally (requires .env file with all env vars set)
python -m bot.main

# Docker (primary deployment method)
docker compose up -d --build      # Build and start
docker compose logs -f            # Tail logs
docker compose down               # Stop

# Install dependencies
pip install -r requirements.txt
```

No test framework is configured yet. All code is async Python — use `asyncio` patterns throughout.

---

# Discord ↔ Trello Sync Bot

## Project Overview

A self-hosted Discord bot that bridges a Discord forum channel with a Trello board. When posts are created in a designated Discord forum channel, cards are automatically created on Trello. Card movements in Trello update tags on the Discord thread. Comments flow bidirectionally between both platforms.

The bot is deployed via Docker and uses SQLite to persist the Discord thread ↔ Trello card mapping across restarts.

---

## Tech Stack

- **Language:** Python 3.11+
- **Discord library:** `discord.py` (v2.x) — required for forum channel / thread support
- **Trello API:** Direct REST calls via `httpx` (async) — no wrapper library
- **Database:** SQLite via `aiosqlite` (async)
- **HTTP server:** `aiohttp` (for health check endpoint only)
- **Config:** Environment variables loaded via `python-dotenv`
- **Containerisation:** Docker + Docker Compose

---

## Repository Structure

```
discord-trello-bot/
├── CLAUDE.md
├── README.md
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── bot/
│   ├── __init__.py
│   ├── main.py               # Entry point — sets up bot, starts poller
│   ├── config.py             # Loads and validates all env vars
│   ├── database.py           # SQLite schema + all DB helpers
│   ├── discord_handler.py    # All discord.py event listeners
│   ├── trello_client.py      # All Trello REST API calls
│   ├── sync.py               # Core bidirectional sync logic
│   └── poller.py             # Background polling loop for Trello changes
└── data/                     # Mount point for SQLite file (persisted via Docker volume)
    └── .gitkeep
```

---

## Environment Variables

All configuration is via environment variables. Never hardcode secrets.

```env
# Discord
DISCORD_BOT_TOKEN=          # Bot token from Discord Developer Portal
DISCORD_FORUM_CHANNEL_ID=   # ID of the forum channel to watch (single channel)
                            # To watch multiple channels, comma-separate IDs

# Trello
TRELLO_API_KEY=             # From https://trello.com/app-key
TRELLO_API_TOKEN=           # OAuth token generated from the above key
TRELLO_BOARD_ID=            # ID of the target Trello board
TRELLO_MEMBER_ID=           # Your Trello member ID (used to scope polling)

# Trello List Names (must match exactly, case-sensitive)
TRELLO_LIST_TODO=To Do
TRELLO_LIST_IN_PROGRESS=In Progress
TRELLO_LIST_TESTING=Testing
TRELLO_LIST_COMPLETE=Complete
TRELLO_LIST_PUBLISHED=Published

# Discord Tag Names (must match exactly, case-sensitive forum tags)
DISCORD_TAG_IN_PROGRESS=In Progress
DISCORD_TAG_TESTING=Testing
DISCORD_TAG_COMPLETE=Complete
DISCORD_TAG_PUBLISHED=Published

# Bot Behaviour
TRELLO_POLL_INTERVAL_SECONDS=30   # How often to poll Trello for changes
MAX_ATTACHMENT_SIZE_MB=10         # Attachments larger than this are skipped with a note on the card
BOT_COMMENT_PREFIX=[Trello]       # Prefix added to Discord messages that originate from Trello

# Paths
DB_PATH=/data/bot.db              # SQLite database location (inside container)
```

---

## Database Schema

Managed in `database.py`. Migrations run automatically on startup.

### `thread_card_map`
Maps Discord forum threads to Trello cards.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `discord_thread_id` | TEXT UNIQUE | Discord thread/post ID (string) |
| `trello_card_id` | TEXT UNIQUE | Trello card ID |
| `discord_channel_id` | TEXT | Parent forum channel ID |
| `created_at` | DATETIME | Row creation timestamp |

### `synced_comments`
Tracks which comments have already been synced to prevent duplicates.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `source` | TEXT | `"discord"` or `"trello"` |
| `source_id` | TEXT | Discord message ID or Trello action ID |
| `trello_card_id` | TEXT | Associated Trello card |
| `discord_thread_id` | TEXT | Associated Discord thread |
| `synced_at` | DATETIME | When sync occurred |

### `card_state_cache`
Caches last-known Trello card list to detect list changes during polling.

| Column | Type | Description |
|---|---|---|
| `trello_card_id` | TEXT PK | Trello card ID |
| `list_id` | TEXT | Last known list ID |
| `updated_at` | DATETIME | When cache was last updated |

---

## Core Flows

### 1. New Discord Forum Post → Trello Card

**Trigger:** `discord.py` `on_thread_create` event on the watched forum channel.

**Steps:**
1. Extract thread title, starter message body, and any attachments from the first message in the thread.
2. Call `trello_client.create_card()` in the To Do list with:
   - **Name:** thread title
   - **Description:** message body + footer with link back to Discord thread
   - **Attachments:** download each Discord attachment (respecting `MAX_ATTACHMENT_SIZE_MB`), then upload to Trello via the card attachment API. If an attachment exceeds the size limit, append a note to the card description with the original Discord URL instead.
3. Save the `(discord_thread_id, trello_card_id)` mapping to `thread_card_map`.
4. Cache the card's initial list ID in `card_state_cache`.

**Error handling:** If Trello card creation fails, log the error. Do not crash the bot. Optionally send an ephemeral message or tag the post with an "Error" tag if one is configured.

---

### 2. Trello Card Moved → Discord Thread Tag Update

**Trigger:** Background poller in `poller.py` runs every `TRELLO_POLL_INTERVAL_SECONDS`.

**Polling logic:**
1. For every row in `thread_card_map`, fetch the current card from Trello (`GET /cards/{id}?fields=idList`).
2. Compare `idList` against `card_state_cache`.
3. If the list has changed, call `sync.handle_card_moved(card_id, new_list_id)`.
4. Update `card_state_cache` with the new list ID.

**`handle_card_moved` behaviour by destination list:**

| Trello List | Discord Action |
|---|---|
| In Progress | Remove all managed tags; apply **In Progress** tag |
| Testing | Remove all managed tags; apply **Testing** tag |
| Complete | Remove all managed tags; apply **Complete** tag |
| Published | Remove all managed tags; apply **Published** tag |
| To Do | Remove all managed tags (no tag applied) |

"Managed tags" means only the four tags defined in env vars (`DISCORD_TAG_*`). Do not touch any user-applied tags that are not in the managed set.

**Applying Discord forum tags:**
- Use `discord.py`'s `Thread.edit(applied_tags=[...])` to update tags on the forum thread.
- Look up available tags via `ForumChannel.available_tags` and match by name. If a configured tag name doesn't exist on the channel, log a warning and skip (do not crash).

---

### 3. Trello Comment → Discord Thread Message

**Trigger:** Poller detects new comments on tracked Trello cards.

**Polling logic:**
1. For each card in `thread_card_map`, call `GET /cards/{id}/actions?filter=commentCard`.
2. For each comment action, check if `action.id` is already in `synced_comments` (source = `"trello"`).
3. If not synced, post the comment to the corresponding Discord thread as a message:
   ```
   [Trello] AuthorName: comment body here
   ```
4. Record the action ID in `synced_comments`.

**Important:** When the bot itself posts to Discord (step 3), the resulting Discord message will trigger `on_message`. The bot must ignore messages it posted itself (check `message.author == bot.user`).

---

### 4. Discord Thread Message → Trello Comment

**Trigger:** `discord.py` `on_message` event.

**Steps:**
1. Check that the message is in a thread that exists in `thread_card_map`.
2. Ignore messages from the bot itself (`message.author.bot`).
3. Ignore the thread's starter message (it was already synced when the card was created).
4. Check if `message.id` is already in `synced_comments` (source = `"discord"`) — skip if so.
5. Call `trello_client.add_comment()` with the text:
   ```
   **DiscordUsername:** message content here
   ```
6. Record the message ID in `synced_comments`.

**Attachments in Discord replies:** If the message contains attachments, append the direct Discord CDN URLs to the Trello comment body. Do not re-upload these (only the original post's attachments are uploaded to Trello).

---

## Trello API Client (`trello_client.py`)

All methods are async. Use `httpx.AsyncClient` with a shared session. Base URL: `https://api.trello.com/1`.

Auth params `key` and `token` are appended to every request.

Key methods to implement:

```python
async def get_lists(board_id: str) -> list[dict]
async def create_card(list_id: str, name: str, desc: str) -> dict
async def get_card(card_id: str) -> dict
async def get_card_actions(card_id: str, filter: str = "commentCard") -> list[dict]
async def add_comment(card_id: str, text: str) -> dict
async def add_attachment(card_id: str, filename: str, data: bytes, mime_type: str) -> dict
async def resolve_list_ids(board_id: str) -> dict[str, str]  # Returns {list_name: list_id}
```

List IDs are resolved once on startup and cached in memory (they don't change at runtime).

---

## Discord Bot Setup (`discord_handler.py`)

Required bot intents:
```python
intents = discord.Intents.default()
intents.message_content = True   # Needed to read message bodies
intents.guilds = True
intents.members = False           # Not needed
```

Required OAuth2 bot permissions when adding to server:
- Read Messages / View Channels
- Send Messages
- Read Message History
- Manage Threads (needed to edit thread tags)
- Attach Files

Events to handle:
- `on_ready` — log startup, resolve Trello list IDs, start poller
- `on_thread_create` — handle new forum posts
- `on_message` — handle new messages in tracked threads

---

## Poller (`poller.py`)

Runs as an `asyncio` background task started in `on_ready`.

```python
async def poll_loop():
    while True:
        try:
            await sync.poll_trello_changes()
        except Exception as e:
            logger.error(f"Poller error: {e}")
        await asyncio.sleep(TRELLO_POLL_INTERVAL_SECONDS)
```

`poll_trello_changes()` in `sync.py` handles both comment syncing and list-change detection in a single pass per card to minimise API calls.

**Trello API rate limits:** Trello allows ~100 requests per 10 seconds per token. With 30s polling and batched fetches, this is not a concern for typical board sizes (< 200 active cards). If the board grows large, add a small `asyncio.sleep(0.1)` between card fetches.

---

## Docker Setup

### `Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

CMD ["python", "-m", "bot.main"]
```

### `docker-compose.yml`
```yaml
version: "3.9"

services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/data   # Persists SQLite database
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Running the bot
```bash
cp .env.example .env
# Fill in .env values
docker compose up -d --build

# Logs
docker compose logs -f

# Stop
docker compose down
```

---

## Configuration Notes & Assumptions

These are defaults chosen during spec — adjust as needed:

1. **Single forum channel watched by default.** To watch multiple channels, `DISCORD_FORUM_CHANNEL_ID` accepts comma-separated IDs. The code should split and watch all of them.
2. **Trello list names are configurable** via env vars to avoid hardcoding. If your lists are named differently (e.g. "Done" instead of "Complete"), update the env vars — no code changes needed.
3. **Bot-originated Discord messages are prefixed** with `[Trello]` so users can distinguish them. Configurable via `BOT_COMMENT_PREFIX`.
4. **If a Trello card is deleted:** the orphaned row in `thread_card_map` stays. The poller will log a 404 warning and skip that card. No automated Discord action is taken. Consider adding a periodic cleanup job if needed.
5. **Thread starter message exclusion:** The first message of a forum post (the body) is not re-synced as a comment — it was already used to populate the card description at creation time.
6. **Attachments over the size limit** result in the Discord CDN URL being appended to the card description with a note, rather than being silently dropped.
7. **Tags must be pre-created** on the Discord forum channel before the bot starts. The bot looks them up by name — it does not create them.

---

## Known Limitations / Future Improvements

- **Trello → Discord edits:** If a Trello card description or comment is edited, the change is not reflected in Discord. Bidirectional edits are out of scope for v1.
- **Discord message edits → Trello:** Not synced in v1.
- **Multiple boards:** Only one Trello board is supported. Multi-board support would require schema changes.
- **Webhook mode:** Switching from polling to Trello webhooks (requires a public URL/reverse proxy like Caddy or Cloudflare Tunnel) would reduce latency and API calls significantly. The architecture is designed so `poller.py` can be swapped for a webhook receiver without changing `sync.py`.
