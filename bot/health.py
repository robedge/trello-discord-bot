# bot/health.py
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    import discord

    from bot.config import Config
    from bot.database import Database
    from bot.trello_client import TrelloClient

logger = logging.getLogger(__name__)

DISCORD_MAX_MESSAGE_LENGTH = 2000


def _split_message(content: str) -> list[str]:
    """Split content into chunks that fit Discord's 2000-char limit.

    Splits at ## section boundaries first. If a single section exceeds
    the limit, splits at bullet point boundaries within that section.
    """
    if len(content) <= DISCORD_MAX_MESSAGE_LENGTH:
        return [content]

    # Split at ## headers (keep the header with its section)
    sections = re.split(r"(?=\n## )", content)

    chunks: list[str] = []
    current = ""

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # If adding this section would exceed the limit
        if current and len(current) + len(section) + 2 > DISCORD_MAX_MESSAGE_LENGTH:
            if current.strip():
                chunks.append(current.strip())
            current = section
        elif not current and len(section) > DISCORD_MAX_MESSAGE_LENGTH:
            # Single section exceeds limit — split at bullet points
            lines = section.split("\n")
            sub_chunk = ""
            for line in lines:
                if sub_chunk and len(sub_chunk) + len(line) + 1 > DISCORD_MAX_MESSAGE_LENGTH:
                    chunks.append(sub_chunk.strip())
                    sub_chunk = line
                else:
                    sub_chunk += ("\n" if sub_chunk else "") + line
            if sub_chunk.strip():
                current = sub_chunk
            continue
        else:
            current += ("\n\n" if current else "") + section

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [content]


def create_health_app(
    db: Database,
    trello: TrelloClient,
    bot: discord.Client | None = None,
    config: Config | None = None,
) -> web.Application:
    async def health_handler(request: web.Request) -> web.Response:
        db_ok = await db.check_health()
        trello_ok = await trello.check_health()

        if db_ok and trello_ok:
            return web.json_response({"status": "healthy"})

        return web.json_response(
            {
                "status": "unhealthy",
                "details": {
                    "database": db_ok,
                    "trello": trello_ok,
                },
            },
            status=503,
        )

    async def publish_release_handler(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        version = body.get("version")
        content = body.get("content")

        if not version or not content:
            return web.json_response(
                {"error": "Missing required fields: version, content"}, status=400
            )

        if not config or not config.discord_announcements_channel_id:
            return web.json_response(
                {"error": "Announcements channel not configured"}, status=500
            )

        if not bot:
            return web.json_response(
                {"error": "Discord bot not available"}, status=500
            )

        channel = bot.get_channel(config.discord_announcements_channel_id)
        if not channel:
            return web.json_response(
                {"error": f"Channel {config.discord_announcements_channel_id} not found"},
                status=500,
            )

        chunks = _split_message(content)
        message_ids: list[int] = []

        try:
            for chunk in chunks:
                msg = await channel.send(chunk)
                message_ids.append(msg.id)
        except Exception as e:
            logger.error("Failed to send release notes to Discord: %s", e)
            return web.json_response(
                {"error": f"Discord send failed: {e}"}, status=500
            )

        logger.info(
            "Published v%s release notes: %d message(s) to channel %s",
            version,
            len(message_ids),
            config.discord_announcements_channel_id,
        )

        return web.json_response({"status": "ok", "message_ids": message_ids})

    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_post("/publish-release", publish_release_handler)
    return app
