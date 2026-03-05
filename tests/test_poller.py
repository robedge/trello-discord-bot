# tests/test_poller.py
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from bot.poller import start_poller


@pytest.mark.asyncio
async def test_poller_calls_poll(monkeypatch):
    sync_service = AsyncMock()
    sync_service.poll_trello_changes = AsyncMock()

    call_count = 0

    async def fake_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    task = start_poller(sync_service, poll_interval=5)
    try:
        await task
    except asyncio.CancelledError:
        pass

    sync_service.poll_trello_changes.assert_awaited_once()
