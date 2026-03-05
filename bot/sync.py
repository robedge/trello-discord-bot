from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord
    from bot.config import Config
    from bot.database import Database
    from bot.trello_client import TrelloClient

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(
        self,
        db: Database,
        trello: TrelloClient,
        bot: discord.Client,
        config: Config,
    ) -> None:
        self.db = db
        self.trello = trello
        self.bot = bot
        self.config = config

    async def poll_trello_changes(self) -> None:
        mappings = await self.db.get_all_mappings()
        if not mappings:
            return

        for mapping in mappings:
            try:
                await self._process_card(mapping)
            except Exception as e:
                logger.error(
                    "Error processing card %s: %s",
                    mapping["trello_card_id"],
                    e,
                )
            await asyncio.sleep(0.1)

    async def _process_card(self, mapping: dict) -> None:
        card_id = mapping["trello_card_id"]
        thread_id = mapping["discord_thread_id"]

        try:
            card = await self.trello.get_card(card_id)
        except Exception as e:
            logger.warning("Could not fetch card %s (maybe deleted): %s", card_id, e)
            return

        # Check if card was archived → delete Discord thread
        if card.get("closed"):
            thread = self.bot.get_channel(int(thread_id))
            if thread is not None:
                try:
                    await thread.delete()
                    logger.info("Deleted thread %s (Trello card %s archived)", thread_id, card_id)
                except Exception as e:
                    logger.error("Failed to delete thread %s: %s", thread_id, e)
            return

        # Check for list change
        current_list_id = card["idList"]
        cached_list_id = await self.db.get_cached_list_id(card_id)

        if cached_list_id and current_list_id != cached_list_id:
            await self._handle_card_moved(thread_id, current_list_id)
            await self.db.update_cached_list_id(card_id, current_list_id)
        elif not cached_list_id:
            await self.db.update_cached_list_id(card_id, current_list_id)

        # Check for new comments
        actions = await self.trello.get_card_actions(card_id)
        for action in actions:
            action_id = action["id"]
            if await self.db.is_comment_synced("trello", action_id):
                continue

            author = action.get("memberCreator", {}).get("fullName", "Unknown")
            text = action.get("data", {}).get("text", "")
            prefix = self.config.bot_comment_prefix

            thread = self.bot.get_channel(int(thread_id))
            if thread is None:
                logger.warning("Discord thread %s not found", thread_id)
                continue

            prefix = self.config.bot_comment_prefix
            msg = f"{prefix} {text}" if prefix else text
            await thread.send(msg)
            await self.db.add_synced_comment("trello", action_id, card_id, thread_id)

    async def _handle_card_moved(self, thread_id: str, new_list_id: str) -> None:
        list_name = self.trello.get_list_name(new_list_id)
        if list_name is None:
            logger.warning("Unknown list ID: %s", new_list_id)
            return

        tag_name = self.config.list_to_tag_map.get(list_name)
        managed_names = set(self.config.managed_tag_names)

        thread = self.bot.get_channel(int(thread_id))
        if thread is None:
            logger.warning("Discord thread %s not found for tag update", thread_id)
            return

        channel = thread.parent
        if channel is None:
            logger.warning("Could not find parent channel for thread %s", thread_id)
            return

        available_tags = {t.name: t for t in channel.available_tags}

        # Keep non-managed tags
        new_tags = [t for t in thread.applied_tags if t.name not in managed_names]

        # Add the target tag if applicable
        if tag_name and tag_name in available_tags:
            new_tags.append(available_tags[tag_name])
        elif tag_name:
            logger.warning("Tag '%s' not found on channel, skipping", tag_name)

        # Close/archive the thread if the card moved to a completed list
        should_close = list_name in self.config.close_thread_lists
        await thread.edit(applied_tags=new_tags, archived=should_close)
        if should_close:
            logger.info("Closed thread %s (card moved to '%s')", thread_id, list_name)
        else:
            logger.info("Updated thread %s tags for list '%s'", thread_id, list_name)
