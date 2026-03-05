# Discord-Trello Sync Bot

A self-hosted bot that bridges Discord forum channels with a Trello board. Forum posts become Trello cards, card movements update Discord thread tags, and comments sync bidirectionally.

## What It Does

- **New forum post** creates a Trello card in the "To Do" list, with attachments
- **Card moved in Trello** updates the Discord thread's tag (In Progress, Testing, Complete, Published)
- **Card moved to Published** closes the Discord thread
- **Comments** sync both ways between Discord threads and Trello cards
- **Discord thread deleted** archives the linked Trello card
- **Trello card archived** deletes the linked Discord thread
- **Per-channel prefixes** let you tag card titles like `[BUG] Title` or `[FEAT] Title`
- **Health check endpoint** reports database and Trello API status

## Prerequisites

- Docker and Docker Compose
- A Discord bot token with Message Content privileged intent enabled
- Trello API key and token
- Forum tags pre-created on your Discord forum channel (In Progress, Testing, Complete, Published)

## Setup

### 1. Discord Bot

1. Go to https://discord.com/developers/applications/ and create a new application
2. Go to **Bot** > enable **Message Content Intent** under Privileged Gateway Intents
3. Copy the bot token
4. Go to **OAuth2** > **URL Generator**, select scopes `bot`, and permissions:
   - Read Messages / View Channels
   - Send Messages
   - Read Message History
   - Manage Threads
   - Attach Files
5. Use the generated URL to invite the bot to your server

### 2. Trello API

1. Go to https://trello.com/app-key to get your API key
2. Click "Generate a Token" on that page and authorize it
3. Get your board ID from the Trello board URL: `trello.com/b/<BOARD_ID>/...`
4. Get your member ID by visiting `https://api.trello.com/1/members/me?key=YOUR_KEY&token=YOUR_TOKEN`

### 3. Configuration

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
# Required
DISCORD_BOT_TOKEN=your-bot-token
DISCORD_FORUM_CHANNEL_ID=123456789          # Right-click channel > Copy Channel ID
TRELLO_API_KEY=your-api-key
TRELLO_API_TOKEN=your-api-token
TRELLO_BOARD_ID=your-board-id
TRELLO_MEMBER_ID=your-member-id

# Path (must be absolute inside container)
DB_PATH=/data/bot.db
```

To watch multiple forum channels, comma-separate the IDs:

```env
DISCORD_FORUM_CHANNEL_ID=123456789,987654321
```

To add title prefixes per channel:

```env
DISCORD_CHANNEL_PREFIXES=123456789:BUG,987654321:FEAT
```

This produces card titles like `[BUG] Login broken` and `[FEAT] Dark mode`.

### 4. Trello List Names

The bot matches list names exactly (case-sensitive). If your board uses different names, update these:

```env
TRELLO_LIST_TODO=To Do
TRELLO_LIST_IN_PROGRESS=In Progress
TRELLO_LIST_TESTING=Testing
TRELLO_LIST_COMPLETE=Complete
TRELLO_LIST_PUBLISHED=Published
```

### 5. Discord Forum Tags

Create these tags on your Discord forum channel before starting the bot. The names must match exactly:

- In Progress
- Testing
- Complete
- Published

Or customize them in `.env`:

```env
DISCORD_TAG_IN_PROGRESS=In Progress
DISCORD_TAG_TESTING=Testing
DISCORD_TAG_COMPLETE=Complete
DISCORD_TAG_PUBLISHED=Published
```

### 6. Run

```bash
docker compose up -d --build
```

Check the logs:

```bash
docker compose logs -f
```

Stop:

```bash
docker compose down
```

## Health Check

The bot exposes a health endpoint at `http://localhost:8080/health` (port configurable via `HEALTH_PORT`).

```bash
curl http://localhost:8080/health
```

Returns `200` with `{"status": "healthy"}` or `503` with details on what failed (database or Trello API).

## Optional Settings

| Variable | Default | Description |
|---|---|---|
| `TRELLO_POLL_INTERVAL_SECONDS` | `30` | How often to poll Trello for changes |
| `MAX_ATTACHMENT_SIZE_MB` | `10` | Attachments larger than this are linked, not uploaded |
| `BOT_COMMENT_PREFIX` | `[Trello]` | Prefix on Trello comments posted to Discord. Set empty to disable |
| `LOG_LEVEL` | `INFO` | Python log level (DEBUG, INFO, WARNING, ERROR) |
| `HEALTH_PORT` | `8080` | Port for the health check HTTP server |

## How Syncing Works

The bot uses a SQLite database to track which Discord threads map to which Trello cards, and which comments have already been synced (to prevent duplicates).

**Discord to Trello** happens in real time via Discord event listeners. **Trello to Discord** happens via polling (every 30 seconds by default) since the Trello API is used without webhooks.

The bot only syncs forward from when it starts. Existing threads without cards are not backfilled.

## Data Persistence

The SQLite database is stored at `./data/bot.db` on the host (mounted into the container at `/data/bot.db`). This file persists across container restarts. Do not delete it unless you want to lose all thread-to-card mappings.

## Limitations

- One Trello board per bot instance
- Edits to messages or comments are not synced (only new ones)
- No webhook mode (polling only) — switching to webhooks would require a public URL
