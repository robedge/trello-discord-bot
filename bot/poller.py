# bot/poller.py
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.sync import SyncService

logger = logging.getLogger(__name__)


async def _poll_loop(sync_service: SyncService, poll_interval: int) -> None:
    while True:
        try:
            await sync_service.poll_trello_changes()
        except Exception as e:
            logger.error("Poller error: %s", e)
        await asyncio.sleep(poll_interval)


def start_poller(sync_service: SyncService, poll_interval: int = 30) -> asyncio.Task:
    logger.info("Starting Trello poller (interval: %ds)", poll_interval)
    return asyncio.create_task(_poll_loop(sync_service, poll_interval))
