from __future__ import annotations

import os
from dataclasses import dataclass


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise ValueError(f"Missing required environment variable: {name}")
    return val


@dataclass
class Config:
    discord_bot_token: str
    discord_forum_channel_ids: list[int]
    trello_api_key: str
    trello_api_token: str
    trello_board_id: str
    trello_member_id: str

    # Trello list names
    trello_list_todo: str = "To Do"
    trello_list_in_progress: str = "In Progress"
    trello_list_testing: str = "Testing"
    trello_list_complete: str = "Complete"
    trello_list_published: str = "Published"

    # Discord tag names
    discord_tag_in_progress: str = "In Progress"
    discord_tag_testing: str = "Testing"
    discord_tag_complete: str = "Complete"
    discord_tag_published: str = "Published"

    # Bot behaviour
    trello_poll_interval_seconds: int = 30
    max_attachment_size_mb: int = 10
    bot_comment_prefix: str = "[Trello]"

    # Paths
    db_path: str = "data/bot.db"

    # Logging
    log_level: str = "INFO"

    # Health check
    health_port: int = 8080

    @classmethod
    def from_env(cls) -> Config:
        discord_bot_token = _require("DISCORD_BOT_TOKEN")
        channel_ids_raw = _require("DISCORD_FORUM_CHANNEL_ID")
        channel_ids = [int(cid.strip()) for cid in channel_ids_raw.split(",")]

        return cls(
            discord_bot_token=discord_bot_token,
            discord_forum_channel_ids=channel_ids,
            trello_api_key=_require("TRELLO_API_KEY"),
            trello_api_token=_require("TRELLO_API_TOKEN"),
            trello_board_id=_require("TRELLO_BOARD_ID"),
            trello_member_id=_require("TRELLO_MEMBER_ID"),
            trello_list_todo=os.environ.get("TRELLO_LIST_TODO", "To Do"),
            trello_list_in_progress=os.environ.get("TRELLO_LIST_IN_PROGRESS", "In Progress"),
            trello_list_testing=os.environ.get("TRELLO_LIST_TESTING", "Testing"),
            trello_list_complete=os.environ.get("TRELLO_LIST_COMPLETE", "Complete"),
            trello_list_published=os.environ.get("TRELLO_LIST_PUBLISHED", "Published"),
            discord_tag_in_progress=os.environ.get("DISCORD_TAG_IN_PROGRESS", "In Progress"),
            discord_tag_testing=os.environ.get("DISCORD_TAG_TESTING", "Testing"),
            discord_tag_complete=os.environ.get("DISCORD_TAG_COMPLETE", "Complete"),
            discord_tag_published=os.environ.get("DISCORD_TAG_PUBLISHED", "Published"),
            trello_poll_interval_seconds=int(os.environ.get("TRELLO_POLL_INTERVAL_SECONDS", "30")),
            max_attachment_size_mb=int(os.environ.get("MAX_ATTACHMENT_SIZE_MB", "10")),
            bot_comment_prefix=os.environ.get("BOT_COMMENT_PREFIX", "[Trello]"),
            db_path=os.environ.get("DB_PATH", "data/bot.db"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            health_port=int(os.environ.get("HEALTH_PORT", "8080")),
        )

    @property
    def managed_tag_names(self) -> list[str]:
        return [
            self.discord_tag_in_progress,
            self.discord_tag_testing,
            self.discord_tag_complete,
            self.discord_tag_published,
        ]

    @property
    def list_to_tag_map(self) -> dict[str, str | None]:
        """Maps Trello list names to Discord tag names. None means remove all managed tags."""
        return {
            self.trello_list_todo: None,
            self.trello_list_in_progress: self.discord_tag_in_progress,
            self.trello_list_testing: self.discord_tag_testing,
            self.trello_list_complete: self.discord_tag_complete,
            self.trello_list_published: self.discord_tag_published,
        }

    @property
    def close_thread_lists(self) -> set[str]:
        """Trello list names that should close/archive the Discord thread."""
        return {self.trello_list_published}
