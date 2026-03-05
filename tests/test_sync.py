import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.sync import SyncService
from bot.database import Database
from bot.config import Config


@pytest.fixture
def config():
    return Config(
        discord_bot_token="t",
        discord_forum_channel_ids=[100],
        trello_api_key="k",
        trello_api_token="tok",
        trello_board_id="board1",
        trello_member_id="m",
    )


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=Database)
    db.get_all_mappings = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_trello():
    trello = AsyncMock()
    trello._list_ids = {"To Do": "l1", "In Progress": "l2", "Testing": "l3"}
    trello.get_list_name = MagicMock(
        side_effect=lambda lid: {
            "l1": "To Do",
            "l2": "In Progress",
            "l3": "Testing",
        }.get(lid)
    )
    return trello


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    return bot


@pytest.fixture
def sync_service(mock_db, mock_trello, mock_bot, config):
    return SyncService(mock_db, mock_trello, mock_bot, config)


@pytest.mark.asyncio
async def test_poll_no_mappings(sync_service, mock_db):
    """Poll with no mappings should do nothing."""
    mock_db.get_all_mappings.return_value = []
    await sync_service.poll_trello_changes()
    mock_db.get_all_mappings.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_detects_list_change(sync_service, mock_db, mock_trello, mock_bot):
    mock_db.get_all_mappings.return_value = [
        {"discord_thread_id": "111", "trello_card_id": "c1", "discord_channel_id": "200"}
    ]
    mock_trello.get_card.return_value = {"idList": "l2"}
    mock_trello.get_card_actions.return_value = []
    mock_db.get_cached_list_id.return_value = "l1"

    # Mock Discord objects
    mock_tag = MagicMock()
    mock_tag.name = "In Progress"
    mock_tag.id = 1
    mock_channel = MagicMock()
    mock_channel.available_tags = [mock_tag]
    mock_thread = AsyncMock()
    mock_thread.applied_tags = []
    mock_thread.parent = mock_channel
    mock_bot.get_channel = MagicMock(return_value=mock_thread)

    await sync_service.poll_trello_changes()

    mock_db.update_cached_list_id.assert_awaited_with("c1", "l2")
    mock_thread.edit.assert_awaited_once()
    # "In Progress" is not a close list, so archived should be False
    edit_kwargs = mock_thread.edit.call_args[1]
    assert edit_kwargs["archived"] is False


@pytest.mark.asyncio
async def test_poll_closes_thread_on_published(sync_service, mock_db, mock_trello, mock_bot):
    """When a card moves to Published, the Discord thread should be archived."""
    mock_trello.get_list_name = MagicMock(
        side_effect=lambda lid: {"l1": "To Do", "l5": "Published"}.get(lid)
    )
    mock_db.get_all_mappings.return_value = [
        {"discord_thread_id": "111", "trello_card_id": "c1", "discord_channel_id": "200"}
    ]
    mock_trello.get_card.return_value = {"idList": "l5"}
    mock_trello.get_card_actions.return_value = []
    mock_db.get_cached_list_id.return_value = "l1"

    mock_tag = MagicMock()
    mock_tag.name = "Published"
    mock_tag.id = 5
    mock_channel = MagicMock()
    mock_channel.available_tags = [mock_tag]
    mock_thread = AsyncMock()
    mock_thread.applied_tags = []
    mock_thread.parent = mock_channel
    mock_bot.get_channel = MagicMock(return_value=mock_thread)

    await sync_service.poll_trello_changes()

    edit_kwargs = mock_thread.edit.call_args[1]
    assert edit_kwargs["archived"] is True


@pytest.mark.asyncio
async def test_poll_syncs_new_trello_comment(sync_service, mock_db, mock_trello, mock_bot):
    mock_db.get_all_mappings.return_value = [
        {"discord_thread_id": "111", "trello_card_id": "c1", "discord_channel_id": "200"}
    ]
    mock_trello.get_card.return_value = {"idList": "l1"}
    mock_trello.get_card_actions.return_value = [
        {
            "id": "action1",
            "memberCreator": {"fullName": "Alice"},
            "data": {"text": "hello from trello"},
        }
    ]
    mock_db.get_cached_list_id.return_value = "l1"  # No list change
    mock_db.is_comment_synced.return_value = False

    mock_thread = AsyncMock()
    mock_bot.get_channel = MagicMock(return_value=mock_thread)

    await sync_service.poll_trello_changes()

    mock_thread.send.assert_awaited_once()
    sent_text = mock_thread.send.call_args[0][0]
    assert sent_text == "[Trello] hello from trello"
    mock_db.add_synced_comment.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_skips_already_synced_comment(sync_service, mock_db, mock_trello, mock_bot):
    mock_db.get_all_mappings.return_value = [
        {"discord_thread_id": "111", "trello_card_id": "c1", "discord_channel_id": "200"}
    ]
    mock_trello.get_card.return_value = {"idList": "l1"}
    mock_trello.get_card_actions.return_value = [
        {"id": "action1", "memberCreator": {"fullName": "Alice"}, "data": {"text": "old"}}
    ]
    mock_db.get_cached_list_id.return_value = "l1"
    mock_db.is_comment_synced.return_value = True

    mock_thread = AsyncMock()
    mock_bot.get_channel = MagicMock(return_value=mock_thread)

    await sync_service.poll_trello_changes()

    mock_thread.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_poll_comment_no_prefix_when_empty(mock_db, mock_trello, mock_bot):
    """When bot_comment_prefix is empty, just send the raw comment text."""
    no_prefix_config = Config(
        discord_bot_token="t",
        discord_forum_channel_ids=[100],
        trello_api_key="k",
        trello_api_token="tok",
        trello_board_id="board1",
        trello_member_id="m",
        bot_comment_prefix="",
    )
    svc = SyncService(mock_db, mock_trello, mock_bot, no_prefix_config)

    mock_db.get_all_mappings.return_value = [
        {"discord_thread_id": "111", "trello_card_id": "c1", "discord_channel_id": "200"}
    ]
    mock_trello.get_card.return_value = {"idList": "l1"}
    mock_trello.get_card_actions.return_value = [
        {"id": "a1", "memberCreator": {"fullName": "Bob"}, "data": {"text": "just the text"}}
    ]
    mock_db.get_cached_list_id.return_value = "l1"
    mock_db.is_comment_synced.return_value = False

    mock_thread = AsyncMock()
    mock_bot.get_channel = MagicMock(return_value=mock_thread)

    await svc.poll_trello_changes()

    sent_text = mock_thread.send.call_args[0][0]
    assert sent_text == "just the text"
