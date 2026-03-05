# tests/test_health.py
import pytest
from unittest.mock import AsyncMock
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
