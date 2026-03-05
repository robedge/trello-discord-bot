import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.discord_handler import handle_thread_create, handle_thread_delete, handle_message
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
    return AsyncMock()


@pytest.fixture
def mock_trello():
    trello = AsyncMock()
    trello.get_list_id = MagicMock(return_value="l1")
    return trello


@pytest.mark.asyncio
async def test_handle_thread_create_in_watched_channel(mock_db, mock_trello, config):
    thread = AsyncMock()
    thread.parent_id = 100
    thread.id = 999
    thread.name = "Bug report"
    thread.jump_url = "https://discord.com/channels/1/2/3"

    starter = AsyncMock()
    starter.content = "Description of the bug"
    starter.attachments = []
    thread.fetch_message = AsyncMock(return_value=starter)

    mock_trello.create_card.return_value = {"id": "card1", "idList": "l1"}

    await handle_thread_create(thread, mock_db, mock_trello, config)

    mock_trello.create_card.assert_awaited_once()
    call_args = mock_trello.create_card.call_args
    assert call_args[0][1] == "Bug report"  # name
    mock_db.add_mapping.assert_awaited_once_with("999", "card1", "100")
    mock_db.update_cached_list_id.assert_awaited_once_with("card1", "l1")


@pytest.mark.asyncio
async def test_handle_thread_create_ignores_other_channels(mock_db, mock_trello, config):
    thread = AsyncMock()
    thread.parent_id = 999  # Not a watched channel

    await handle_thread_create(thread, mock_db, mock_trello, config)

    mock_trello.create_card.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_message_syncs_to_trello(mock_db, mock_trello, config):
    message = MagicMock()
    message.author.bot = False
    message.channel.id = 555
    message.id = 888
    message.content = "A reply"
    message.attachments = []
    message.author.display_name = "User1"

    mock_db.get_card_id_for_thread.return_value = "card1"
    mock_db.is_comment_synced.return_value = False
    mock_trello.add_comment.return_value = {"id": "trello_action_1"}

    await handle_message(message, mock_db, mock_trello, config)

    mock_trello.add_comment.assert_awaited_once()
    comment_text = mock_trello.add_comment.call_args[0][1]
    assert "User1" in comment_text
    assert "A reply" in comment_text
    # Should record both Discord and Trello action IDs to prevent echo-back
    assert mock_db.add_synced_comment.await_count == 2


@pytest.mark.asyncio
async def test_handle_message_ignores_bot(mock_db, mock_trello, config):
    message = MagicMock()
    message.author.bot = True

    await handle_message(message, mock_db, mock_trello, config)

    mock_db.get_card_id_for_thread.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_message_ignores_untracked_thread(mock_db, mock_trello, config):
    message = MagicMock()
    message.author.bot = False
    message.channel.id = 555

    mock_db.get_card_id_for_thread.return_value = None

    await handle_message(message, mock_db, mock_trello, config)

    mock_trello.add_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_message_skips_starter_message(mock_db, mock_trello, config):
    """The starter message ID equals the thread ID -- it should be skipped."""
    message = MagicMock()
    message.author.bot = False
    message.channel.id = 555
    message.id = 555  # Same as thread/channel ID = starter message

    mock_db.get_card_id_for_thread.return_value = "card1"

    await handle_message(message, mock_db, mock_trello, config)

    mock_trello.add_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_thread_delete_archives_card(mock_db, mock_trello, config):
    thread = AsyncMock()
    thread.parent_id = 100
    thread.id = 999

    mock_db.get_card_id_for_thread.return_value = "card1"

    await handle_thread_delete(thread, mock_db, mock_trello, config)

    mock_trello.archive_card.assert_awaited_once_with("card1")


@pytest.mark.asyncio
async def test_handle_thread_delete_ignores_other_channels(mock_db, mock_trello, config):
    thread = AsyncMock()
    thread.parent_id = 999

    await handle_thread_delete(thread, mock_db, mock_trello, config)

    mock_trello.archive_card.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_thread_delete_ignores_untracked(mock_db, mock_trello, config):
    thread = AsyncMock()
    thread.parent_id = 100
    thread.id = 999

    mock_db.get_card_id_for_thread.return_value = None

    await handle_thread_delete(thread, mock_db, mock_trello, config)

    mock_trello.archive_card.assert_not_awaited()
