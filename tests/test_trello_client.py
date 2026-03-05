import json
import pytest
import pytest_asyncio
import httpx
from bot.trello_client import TrelloClient


class MockTransport(httpx.AsyncBaseTransport):
    """Records requests and returns canned responses."""

    def __init__(self, responses: list[dict] | None = None):
        self.requests: list[httpx.Request] = []
        self._responses = responses or []
        self._call_count = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return httpx.Response(
                status_code=resp.get("status", 200),
                json=resp.get("json", {}),
            )
        return httpx.Response(200, json={})


@pytest_asyncio.fixture
async def client_and_transport():
    transport = MockTransport()
    client = TrelloClient(api_key="testkey", api_token="testtoken", transport=transport)
    yield client, transport
    await client.close()


@pytest.mark.asyncio
async def test_auth_params_appended(client_and_transport):
    client, transport = client_and_transport
    transport._responses = [{"json": []}]
    await client.get_lists("board1")
    req = transport.requests[0]
    assert b"key=testkey" in req.url.query
    assert b"token=testtoken" in req.url.query


@pytest.mark.asyncio
async def test_get_lists(client_and_transport):
    client, transport = client_and_transport
    transport._responses = [{"json": [{"id": "list1", "name": "To Do"}]}]
    result = await client.get_lists("board1")
    assert result == [{"id": "list1", "name": "To Do"}]


@pytest.mark.asyncio
async def test_create_card(client_and_transport):
    client, transport = client_and_transport
    transport._responses = [{"json": {"id": "card1", "idList": "list1"}}]
    result = await client.create_card("list1", "Title", "Desc")
    assert result["id"] == "card1"
    req = transport.requests[0]
    assert req.method == "POST"


@pytest.mark.asyncio
async def test_resolve_list_ids(client_and_transport):
    client, transport = client_and_transport
    transport._responses = [{"json": [
        {"id": "l1", "name": "To Do"},
        {"id": "l2", "name": "In Progress"},
    ]}]
    result = await client.resolve_list_ids("board1")
    assert result == {"To Do": "l1", "In Progress": "l2"}


@pytest.mark.asyncio
async def test_add_comment(client_and_transport):
    client, transport = client_and_transport
    transport._responses = [{"json": {"id": "action1"}}]
    result = await client.add_comment("card1", "hello")
    assert result["id"] == "action1"
    req = transport.requests[0]
    assert req.method == "POST"
    assert "/cards/card1/actions/comments" in str(req.url)


@pytest.mark.asyncio
async def test_check_health_success(client_and_transport):
    client, transport = client_and_transport
    transport._responses = [{"json": {"id": "member1"}}]
    assert await client.check_health() is True


@pytest.mark.asyncio
async def test_check_health_failure(client_and_transport):
    client, transport = client_and_transport
    transport._responses = [{"status": 401, "json": {"error": "unauthorized"}}]
    assert await client.check_health() is False
