# Discord-Trello Bot: Full Implementation Design

**Date:** 2026-03-04
**Status:** Approved

## Summary

Build a self-hosted Discord bot that syncs a Discord forum channel with a Trello board. New forum posts create Trello cards, card movements update Discord thread tags, and comments flow bidirectionally. Deployed via Docker with SQLite persistence.

## Decisions

- **Architecture:** Monolithic Bot class. Modules are plain functions/classes receiving dependencies. No cogs, no DI framework.
- **Initial sync:** Forward-only. No backfill of existing threads.
- **Error recovery:** Log and skip on Trello API failures. Retry on next poll cycle.
- **Logging:** Python `logging` module with structured format. Level configurable via `LOG_LEVEL` env var.
- **Health check:** Smart `/health` endpoint (checks DB + Trello API reachability).

## Module Design

### `bot/config.py`
Dataclass-based config loaded from env vars via `python-dotenv`. Validates all required vars at startup. `DISCORD_FORUM_CHANNEL_ID` parsed as comma-separated list of ints.

### `bot/database.py`
`Database` class wrapping `aiosqlite`. Three tables as specified in CLAUDE.md: `thread_card_map`, `synced_comments`, `card_state_cache`. Schema created via `CREATE TABLE IF NOT EXISTS` on startup. Helper methods for all CRUD operations. Parameterized queries throughout.

### `bot/trello_client.py`
`TrelloClient` class with `httpx.AsyncClient`. Auth params appended to every request. List IDs resolved once on startup and cached. `add_attachment()` uses multipart upload. All methods raise on HTTP errors; callers handle.

### `bot/discord_handler.py`
`setup_handlers(bot, db, trello_client, config)` registers event listeners:
- `on_ready`: log startup, resolve list IDs, start poller
- `on_thread_create`: create Trello card from new forum post (title, body, attachments), save mapping
- `on_message`: sync Discord thread replies to Trello comments (skip bot messages, skip starter message)

### `bot/sync.py`
Core sync logic:
- `poll_trello_changes()`: single pass per mapped card — fetches card state and comments in one go
- `handle_card_moved()`: maps list ID to tag name, updates Discord thread tags (preserving non-managed tags)
- Trello comment sync: posts unsynced comments to Discord with `[Trello] AuthorName:` prefix

### `bot/poller.py`
`start_poller()` creates an asyncio task. Loop calls `poll_trello_changes()`, catches all exceptions, sleeps for configured interval. Rate limiting: `asyncio.sleep(0.1)` between card fetches for large boards.

### `bot/main.py`
Entry point:
1. Load `.env`, instantiate `Config`, configure logging
2. Create `Database` and `TrelloClient`
3. Create `discord.Bot` with intents (default + message_content + guilds)
4. Register handlers via `setup_handlers()`
5. Start aiohttp health server on port 8080 (`GET /health` checks DB + Trello)
6. `bot.run(token)`
7. Cleanup on shutdown: close DB and httpx session

## Infrastructure

- `requirements.txt`: discord.py>=2.3, httpx>=0.25, aiosqlite>=0.19, aiohttp>=3.9, python-dotenv>=1.0
- `Dockerfile`: python:3.11-slim, installs deps, copies bot/, runs `python -m bot.main`
- `docker-compose.yml`: mounts `./data:/data` for SQLite persistence, env_file `.env`, healthcheck via curl
- `.gitignore`: Python defaults + `.env`, `data/bot.db`
- `.env.example`: all env vars with comments

## Tag Management Rules

- "Managed tags" = the four tags from `DISCORD_TAG_*` env vars
- On card move: remove all managed tags, apply the one matching the destination list (none for "To Do")
- Never touch user-applied tags outside the managed set
- Tags must be pre-created on the Discord forum channel
