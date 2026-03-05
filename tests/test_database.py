import pytest
import pytest_asyncio
from bot.database import Database


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_add_and_get_mapping(db):
    await db.add_mapping("thread1", "card1", "channel1")
    assert await db.get_card_id_for_thread("thread1") == "card1"
    assert await db.get_thread_id_for_card("card1") == "thread1"


@pytest.mark.asyncio
async def test_get_mapping_returns_none_for_unknown(db):
    assert await db.get_card_id_for_thread("unknown") is None
    assert await db.get_thread_id_for_card("unknown") is None


@pytest.mark.asyncio
async def test_synced_comments(db):
    assert await db.is_comment_synced("discord", "msg1") is False
    await db.add_synced_comment("discord", "msg1", "card1", "thread1")
    assert await db.is_comment_synced("discord", "msg1") is True


@pytest.mark.asyncio
async def test_card_state_cache(db):
    assert await db.get_cached_list_id("card1") is None
    await db.update_cached_list_id("card1", "list1")
    assert await db.get_cached_list_id("card1") == "list1"
    await db.update_cached_list_id("card1", "list2")
    assert await db.get_cached_list_id("card1") == "list2"


@pytest.mark.asyncio
async def test_get_all_mappings(db):
    await db.add_mapping("t1", "c1", "ch1")
    await db.add_mapping("t2", "c2", "ch1")
    mappings = await db.get_all_mappings()
    assert len(mappings) == 2
    assert {"discord_thread_id": "t1", "trello_card_id": "c1", "discord_channel_id": "ch1"} in mappings
