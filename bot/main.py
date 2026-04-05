# bot/main.py
from __future__ import annotations

import asyncio
import logging
import os

import discord
from aiohttp import web
from dotenv import load_dotenv

from bot.config import Config
from bot.database import Database
from bot.discord_handler import setup_handlers
from bot.health import create_health_app
from bot.poller import start_poller
from bot.sync import SyncService
from bot.trello_client import TrelloClient

logger = logging.getLogger(__name__)


async def run_health_server(app: web.Application, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health check server listening on port %d", port)
    return runner


def main() -> None:
    load_dotenv()

    config = Config.from_env()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Suppress httpx request logging to avoid leaking credentials in logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True

    bot = discord.Client(intents=intents)
    db = Database(config.db_path)
    trello = TrelloClient(api_key=config.trello_api_key, api_token=config.trello_api_token)

    health_runner: web.AppRunner | None = None
    initialized = False

    @bot.event
    async def on_ready() -> None:
        nonlocal health_runner, initialized
        logger.info("Bot logged in as %s", bot.user)

        if initialized:
            logger.info("on_ready fired again (reconnect), skipping init")
            return
        initialized = True

        await db.init()
        await trello.resolve_list_ids(config.trello_board_id)

        sync_service = SyncService(db, trello, bot, config)
        setup_handlers(bot, db, trello, config)

        start_poller(sync_service, config.trello_poll_interval_seconds)

        health_app = create_health_app(db, trello, bot=bot, config=config)
        health_runner = await run_health_server(health_app, config.health_port)

        logger.info("Bot is ready. Watching %d forum channel(s).", len(config.discord_forum_channel_ids))

    try:
        bot.run(config.discord_bot_token, log_handler=None)
    finally:
        logger.info("Bot shutting down")


if __name__ == "__main__":
    main()
