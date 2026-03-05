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
