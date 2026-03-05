# bot/health.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from bot.database import Database
    from bot.trello_client import TrelloClient

logger = logging.getLogger(__name__)


def create_health_app(db: Database, trello: TrelloClient) -> web.Application:
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

    app = web.Application()
    app.router.add_get("/health", health_handler)
    return app
