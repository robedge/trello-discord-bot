from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info("Database initialized at %s", self.db_path)

    async def _create_tables(self) -> None:
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS thread_card_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_thread_id TEXT UNIQUE NOT NULL,
                trello_card_id TEXT UNIQUE NOT NULL,
                discord_channel_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS synced_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                trello_card_id TEXT NOT NULL,
                discord_thread_id TEXT NOT NULL,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS card_state_cache (
                trello_card_id TEXT PRIMARY KEY,
                list_id TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def add_mapping(
        self, discord_thread_id: str, trello_card_id: str, discord_channel_id: str
    ) -> None:
        await self._conn.execute(
            "INSERT INTO thread_card_map (discord_thread_id, trello_card_id, discord_channel_id) VALUES (?, ?, ?)",
            (discord_thread_id, trello_card_id, discord_channel_id),
        )
        await self._conn.commit()

    async def get_card_id_for_thread(self, discord_thread_id: str) -> str | None:
        cursor = await self._conn.execute(
            "SELECT trello_card_id FROM thread_card_map WHERE discord_thread_id = ?",
            (discord_thread_id,),
        )
        row = await cursor.fetchone()
        return row["trello_card_id"] if row else None

    async def get_thread_id_for_card(self, trello_card_id: str) -> str | None:
        cursor = await self._conn.execute(
            "SELECT discord_thread_id FROM thread_card_map WHERE trello_card_id = ?",
            (trello_card_id,),
        )
        row = await cursor.fetchone()
        return row["discord_thread_id"] if row else None

    async def get_channel_id_for_thread(self, discord_thread_id: str) -> str | None:
        cursor = await self._conn.execute(
            "SELECT discord_channel_id FROM thread_card_map WHERE discord_thread_id = ?",
            (discord_thread_id,),
        )
        row = await cursor.fetchone()
        return row["discord_channel_id"] if row else None

    async def get_all_mappings(self) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT discord_thread_id, trello_card_id, discord_channel_id FROM thread_card_map"
        )
        rows = await cursor.fetchall()
        return [
            {
                "discord_thread_id": row["discord_thread_id"],
                "trello_card_id": row["trello_card_id"],
                "discord_channel_id": row["discord_channel_id"],
            }
            for row in rows
        ]

    async def add_synced_comment(
        self, source: str, source_id: str, trello_card_id: str, discord_thread_id: str
    ) -> None:
        await self._conn.execute(
            "INSERT INTO synced_comments (source, source_id, trello_card_id, discord_thread_id) VALUES (?, ?, ?, ?)",
            (source, source_id, trello_card_id, discord_thread_id),
        )
        await self._conn.commit()

    async def is_comment_synced(self, source: str, source_id: str) -> bool:
        cursor = await self._conn.execute(
            "SELECT 1 FROM synced_comments WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        return await cursor.fetchone() is not None

    async def get_cached_list_id(self, trello_card_id: str) -> str | None:
        cursor = await self._conn.execute(
            "SELECT list_id FROM card_state_cache WHERE trello_card_id = ?",
            (trello_card_id,),
        )
        row = await cursor.fetchone()
        return row["list_id"] if row else None

    async def update_cached_list_id(self, trello_card_id: str, list_id: str) -> None:
        await self._conn.execute(
            """INSERT INTO card_state_cache (trello_card_id, list_id, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(trello_card_id) DO UPDATE SET list_id = ?, updated_at = CURRENT_TIMESTAMP""",
            (trello_card_id, list_id, list_id),
        )
        await self._conn.commit()

    async def check_health(self) -> bool:
        """Returns True if DB is accessible."""
        try:
            cursor = await self._conn.execute("SELECT 1")
            await cursor.fetchone()
            return True
        except Exception:
            return False
