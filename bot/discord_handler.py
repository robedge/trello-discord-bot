from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot.config import Config
    from bot.database import Database
    from bot.trello_client import TrelloClient

logger = logging.getLogger(__name__)


async def handle_thread_create(
    thread: discord.Thread,
    db: Database,
    trello: TrelloClient,
    config: Config,
) -> None:
    if thread.parent_id not in config.discord_forum_channel_ids:
        return

    # Brief delay — on_thread_create fires before the starter message is available
    await asyncio.sleep(1.5)

    try:
        starter = await thread.fetch_message(thread.id)
    except discord.NotFound:
        logger.warning("Could not fetch starter message for thread %s", thread.id)
        return

    desc = starter.content or ""
    desc += f"\n\n---\n[Discord Thread]({thread.jump_url})"

    # Handle attachments
    oversized: list[str] = []
    attachment_data: list[tuple[str, bytes, str]] = []

    for att in starter.attachments:
        if att.size > config.max_attachment_size_mb * 1024 * 1024:
            oversized.append(
                f"- [{att.filename}]({att.url}) (too large: {att.size // 1024 // 1024}MB)"
            )
        else:
            data = await att.read()
            attachment_data.append(
                (att.filename, data, att.content_type or "application/octet-stream")
            )

    if oversized:
        desc += "\n\n**Attachments too large to upload:**\n" + "\n".join(oversized)

    # Get the To Do list ID
    list_id = trello.get_list_id(config.trello_list_todo)
    if not list_id:
        logger.error("Could not find Trello list '%s'", config.trello_list_todo)
        return

    try:
        card_name = config.get_card_name(thread.parent_id, thread.name)
        card = await trello.create_card(list_id, card_name, desc)
    except Exception as e:
        logger.error("Failed to create Trello card for thread %s: %s", thread.id, e)
        return

    card_id = card["id"]

    # Upload attachments
    for filename, data, mime_type in attachment_data:
        try:
            await trello.add_attachment(card_id, filename, data, mime_type)
        except Exception as e:
            logger.error(
                "Failed to upload attachment %s to card %s: %s", filename, card_id, e
            )

    await db.add_mapping(str(thread.id), card_id, str(thread.parent_id))
    await db.update_cached_list_id(card_id, card["idList"])
    logger.info("Created Trello card %s for thread %s", card_id, thread.id)


async def handle_message(
    message: discord.Message,
    db: Database,
    trello: TrelloClient,
    config: Config,
) -> None:
    if message.author.bot:
        return

    thread_id = str(message.channel.id)
    card_id = await db.get_card_id_for_thread(thread_id)
    if not card_id:
        return

    # Skip the starter message (its ID equals the thread ID)
    if message.id == message.channel.id:
        return

    if await db.is_comment_synced("discord", str(message.id)):
        return

    text = f"**{message.author.display_name}:** {message.content}"

    # Append attachment URLs
    if message.attachments:
        urls = "\n".join(f"- {att.url}" for att in message.attachments)
        text += f"\n\n**Attachments:**\n{urls}"

    try:
        result = await trello.add_comment(card_id, text)
    except Exception as e:
        logger.error("Failed to sync message %s to Trello: %s", message.id, e)
        return

    await db.add_synced_comment("discord", str(message.id), card_id, thread_id)
    # Record the Trello action ID to prevent the poller from echoing it back
    if isinstance(result, dict) and "id" in result:
        await db.add_synced_comment("trello", result["id"], card_id, thread_id)
    logger.info("Synced Discord message %s to Trello card %s", message.id, card_id)


def setup_handlers(
    bot: discord.Client,
    db: Database,
    trello: TrelloClient,
    config: Config,
) -> None:
    """Register Discord event handlers on the bot."""

    @bot.event
    async def on_thread_create(thread: discord.Thread) -> None:
        await handle_thread_create(thread, db, trello, config)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        await handle_message(message, db, trello, config)
