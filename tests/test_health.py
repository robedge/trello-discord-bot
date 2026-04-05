# tests/test_health.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web
from bot.health import create_health_app


@pytest.mark.asyncio
async def test_health_healthy():
    db = AsyncMock()
    db.check_health = AsyncMock(return_value=True)
    trello = AsyncMock()
    trello.check_health = AsyncMock(return_value=True)

    app = create_health_app(db, trello)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_unhealthy_db():
    db = AsyncMock()
    db.check_health = AsyncMock(return_value=False)
    trello = AsyncMock()
    trello.check_health = AsyncMock(return_value=True)

    app = create_health_app(db, trello)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 503
        data = await resp.json()
        assert data["status"] == "unhealthy"
        assert data["details"]["database"] is False


@pytest.mark.asyncio
async def test_health_unhealthy_trello():
    db = AsyncMock()
    db.check_health = AsyncMock(return_value=True)
    trello = AsyncMock()
    trello.check_health = AsyncMock(return_value=False)

    app = create_health_app(db, trello)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 503
        data = await resp.json()
        assert data["details"]["trello"] is False


@pytest.mark.asyncio
async def test_publish_release_success():
    """POST /publish-release should send message to announcements channel."""
    db = AsyncMock()
    db.check_health = AsyncMock(return_value=True)
    trello = AsyncMock()
    trello.check_health = AsyncMock(return_value=True)

    mock_channel = AsyncMock()
    mock_message = AsyncMock()
    mock_message.id = 12345
    mock_channel.send = AsyncMock(return_value=mock_message)

    mock_bot = MagicMock()
    mock_bot.get_channel = MagicMock(return_value=mock_channel)

    config = MagicMock()
    config.discord_announcements_channel_id = 999888777

    app = create_health_app(db, trello, bot=mock_bot, config=config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/publish-release",
            json={"version": "1.0.20", "content": "# v1.0.20\n\nRelease notes here"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert len(data["message_ids"]) == 1
        mock_bot.get_channel.assert_called_once_with(999888777)
        mock_channel.send.assert_called_once_with("# v1.0.20\n\nRelease notes here")


@pytest.mark.asyncio
async def test_publish_release_missing_fields():
    """POST /publish-release should return 400 for missing fields."""
    db = AsyncMock()
    db.check_health = AsyncMock(return_value=True)
    trello = AsyncMock()
    trello.check_health = AsyncMock(return_value=True)
    mock_bot = MagicMock()
    config = MagicMock()
    config.discord_announcements_channel_id = 999888777

    app = create_health_app(db, trello, bot=mock_bot, config=config)

    async with TestClient(TestServer(app)) as client:
        # Missing content
        resp = await client.post("/publish-release", json={"version": "1.0.20"})
        assert resp.status == 400

        # Missing version
        resp = await client.post("/publish-release", json={"content": "notes"})
        assert resp.status == 400

        # Empty content
        resp = await client.post("/publish-release", json={"version": "1.0.20", "content": ""})
        assert resp.status == 400


@pytest.mark.asyncio
async def test_publish_release_no_channel_configured():
    """POST /publish-release should return 500 if no announcements channel configured."""
    db = AsyncMock()
    db.check_health = AsyncMock(return_value=True)
    trello = AsyncMock()
    trello.check_health = AsyncMock(return_value=True)
    mock_bot = MagicMock()
    config = MagicMock()
    config.discord_announcements_channel_id = None

    app = create_health_app(db, trello, bot=mock_bot, config=config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/publish-release",
            json={"version": "1.0.20", "content": "# v1.0.20\n\nnotes"},
        )
        assert resp.status == 500
        data = await resp.json()
        assert "not configured" in data["error"]


@pytest.mark.asyncio
async def test_publish_release_splits_long_messages():
    """POST /publish-release should split messages exceeding 2000 chars at ## boundaries."""
    db = AsyncMock()
    db.check_health = AsyncMock(return_value=True)
    trello = AsyncMock()
    trello.check_health = AsyncMock(return_value=True)

    mock_channel = AsyncMock()
    msg1 = AsyncMock()
    msg1.id = 111
    msg2 = AsyncMock()
    msg2.id = 222
    mock_channel.send = AsyncMock(side_effect=[msg1, msg2])

    mock_bot = MagicMock()
    mock_bot.get_channel = MagicMock(return_value=mock_channel)

    config = MagicMock()
    config.discord_announcements_channel_id = 999888777

    # Build content with two sections that together exceed 2000 chars
    section1 = "# v1.0.20\n\n## New Features\n" + "- Feature line\n" * 100
    section2 = "## Bug Fixes\n" + "- Bug fix line\n" * 100
    content = section1 + "\n" + section2

    app = create_health_app(db, trello, bot=mock_bot, config=config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/publish-release",
            json={"version": "1.0.20", "content": content},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert len(data["message_ids"]) == 2
        assert mock_channel.send.call_count == 2
