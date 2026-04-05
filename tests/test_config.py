import os
import pytest
from bot.config import Config


def test_config_loads_required_vars(monkeypatch):
    env = {
        "DISCORD_BOT_TOKEN": "test-token",
        "DISCORD_FORUM_CHANNEL_ID": "123,456",
        "TRELLO_API_KEY": "key",
        "TRELLO_API_TOKEN": "token",
        "TRELLO_BOARD_ID": "board1",
        "TRELLO_MEMBER_ID": "member1",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    config = Config.from_env()
    assert config.discord_bot_token == "test-token"
    assert config.discord_forum_channel_ids == [123, 456]
    assert config.trello_api_key == "key"
    assert config.trello_board_id == "board1"


def test_config_defaults():
    """Defaults are set for optional vars."""
    config = Config(
        discord_bot_token="t",
        discord_forum_channel_ids=[1],
        trello_api_key="k",
        trello_api_token="tok",
        trello_board_id="b",
        trello_member_id="m",
    )
    assert config.trello_poll_interval_seconds == 30
    assert config.max_attachment_size_mb == 10
    assert config.bot_comment_prefix == "[Trello]"
    assert config.db_path == "data/bot.db"
    assert config.log_level == "INFO"
    assert config.health_port == 8080


def test_channel_prefixes(monkeypatch):
    env = {
        "DISCORD_BOT_TOKEN": "t",
        "DISCORD_FORUM_CHANNEL_ID": "100,200",
        "TRELLO_API_KEY": "k",
        "TRELLO_API_TOKEN": "tok",
        "TRELLO_BOARD_ID": "b",
        "TRELLO_MEMBER_ID": "m",
        "DISCORD_CHANNEL_PREFIXES": "100:BUG, 200:FEAT",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    config = Config.from_env()
    assert config.channel_prefixes == {100: "BUG", 200: "FEAT"}
    assert config.get_card_name(100, "Login broken") == "[BUG] Login broken"
    assert config.get_card_name(200, "Dark mode") == "[FEAT] Dark mode"
    assert config.get_card_name(999, "No prefix") == "No prefix"


def test_config_missing_required_var(monkeypatch):
    # Clear all required vars so the first one checked triggers the error
    for var in [
        "DISCORD_BOT_TOKEN",
        "DISCORD_FORUM_CHANNEL_ID",
        "TRELLO_API_KEY",
        "TRELLO_API_TOKEN",
        "TRELLO_BOARD_ID",
        "TRELLO_MEMBER_ID",
    ]:
        monkeypatch.delenv(var, raising=False)
    # Set all except DISCORD_BOT_TOKEN
    monkeypatch.setenv("DISCORD_FORUM_CHANNEL_ID", "123")
    monkeypatch.setenv("TRELLO_API_KEY", "k")
    monkeypatch.setenv("TRELLO_API_TOKEN", "t")
    monkeypatch.setenv("TRELLO_BOARD_ID", "b")
    monkeypatch.setenv("TRELLO_MEMBER_ID", "m")
    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        Config.from_env()


def test_config_announcements_channel_id(monkeypatch):
    """Config should parse DISCORD_ANNOUNCEMENTS_CHANNEL_ID."""
    env = {
        "DISCORD_BOT_TOKEN": "test-token",
        "DISCORD_FORUM_CHANNEL_ID": "123",
        "TRELLO_API_KEY": "key",
        "TRELLO_API_TOKEN": "token",
        "TRELLO_BOARD_ID": "board",
        "TRELLO_MEMBER_ID": "member",
        "DISCORD_ANNOUNCEMENTS_CHANNEL_ID": "999888777",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    config = Config.from_env()
    assert config.discord_announcements_channel_id == 999888777


def test_config_announcements_channel_id_optional(monkeypatch):
    """Config should default to None if DISCORD_ANNOUNCEMENTS_CHANNEL_ID not set."""
    env = {
        "DISCORD_BOT_TOKEN": "test-token",
        "DISCORD_FORUM_CHANNEL_ID": "123",
        "TRELLO_API_KEY": "key",
        "TRELLO_API_TOKEN": "token",
        "TRELLO_BOARD_ID": "board",
        "TRELLO_MEMBER_ID": "member",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("DISCORD_ANNOUNCEMENTS_CHANNEL_ID", raising=False)
    config = Config.from_env()
    assert config.discord_announcements_channel_id is None
