# Discord-Trello Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Discord bot that bidirectionally syncs a forum channel with a Trello board — posts become cards, card movements update tags, comments flow both ways.

**Architecture:** Monolithic Bot class with plain modules receiving dependencies. SQLite for persistence, polling for Trello changes. Forward-only sync (no backfill).

**Tech Stack:** Python 3.11+, discord.py 2.x, httpx (async), aiosqlite, aiohttp (health check), python-dotenv, pytest + pytest-asyncio

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `bot/__init__.py`
- Create: `data/.gitkeep`
- Create: `tests/__init__.py`

**Step 1: Create requirements.txt**

```
discord.py>=2.3,<3.0
httpx>=0.25,<1.0
aiosqlite>=0.19,<1.0
aiohttp>=3.9,<4.0
python-dotenv>=1.0,<2.0
pytest>=7.0
pytest-asyncio>=0.23
```

**Step 2: Create .gitignore**

```
__pycache__/
*.pyc
*.pyo
.env
data/bot.db
*.egg-info/
.venv/
venv/
.pytest_cache/
```

**Step 3: Create .env.example**

```env
# Discord
DISCORD_BOT_TOKEN=
DISCORD_FORUM_CHANNEL_ID=    # Comma-separate for multiple channels

# Trello
TRELLO_API_KEY=
TRELLO_API_TOKEN=
TRELLO_BOARD_ID=
TRELLO_MEMBER_ID=

# Trello List Names (case-sensitive, must match your board)
TRELLO_LIST_TODO=To Do
TRELLO_LIST_IN_PROGRESS=In Progress
TRELLO_LIST_TESTING=Testing
TRELLO_LIST_COMPLETE=Complete
TRELLO_LIST_PUBLISHED=Published

# Discord Tag Names (case-sensitive, must exist on forum channel)
DISCORD_TAG_IN_PROGRESS=In Progress
DISCORD_TAG_TESTING=Testing
DISCORD_TAG_COMPLETE=Complete
DISCORD_TAG_PUBLISHED=Published

# Bot Behaviour
TRELLO_POLL_INTERVAL_SECONDS=30
MAX_ATTACHMENT_SIZE_MB=10
BOT_COMMENT_PREFIX=[Trello]

# Paths
DB_PATH=data/bot.db

# Logging
LOG_LEVEL=INFO

# Health Check
HEALTH_PORT=8080
```

**Step 4: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

CMD ["python", "-m", "bot.main"]
```

**Step 5: Create docker-compose.yml**

```yaml
version: "3.9"

services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/data
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Step 6: Create empty init files and data dir**

```bash
mkdir -p bot tests data
touch bot/__init__.py tests/__init__.py data/.gitkeep
```

**Step 7: Install dependencies and verify**

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Run: `python -c "import discord, httpx, aiosqlite, aiohttp, dotenv; print('OK')"`
Expected: `OK`

**Step 8: Commit**

```bash
git add requirements.txt .gitignore .env.example Dockerfile docker-compose.yml bot/__init__.py tests/__init__.py data/.gitkeep
git commit -m "chore: add project scaffolding"
```

---

### Task 2: Config Module

**Files:**
- Create: `bot/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
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
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        Config.from_env()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.config')

**Step 3: Write implementation**

```python
# bot/config.py
from __future__ import annotations

import os
from dataclasses import dataclass, field


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
        channel_ids_raw = _require("DISCORD_FORUM_CHANNEL_ID")
        channel_ids = [int(cid.strip()) for cid in channel_ids_raw.split(",")]

        return cls(
            discord_bot_token=_require("DISCORD_BOT_TOKEN"),
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
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add bot/config.py tests/test_config.py
git commit -m "feat: add config module with env var loading and validation"
```

---

### Task 3: Database Module

**Files:**
- Create: `bot/database.py`
- Create: `tests/test_database.py`

**Step 1: Write the failing tests**

```python
# tests/test_database.py
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_database.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Write implementation**

```python
# bot/database.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info("Database initialized at %s", self.db_path)

    async def _create_tables(self) -> None:
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS thread_card_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_thread_id TEXT UNIQUE NOT NULL,
                trello_card_id TEXT UNIQUE NOT NULL,
                discord_channel_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS synced_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                trello_card_id TEXT NOT NULL,
                discord_thread_id TEXT NOT NULL,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS card_state_cache (
                trello_card_id TEXT PRIMARY KEY,
                list_id TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def add_mapping(self, discord_thread_id: str, trello_card_id: str, discord_channel_id: str) -> None:
        await self._conn.execute(
            "INSERT INTO thread_card_map (discord_thread_id, trello_card_id, discord_channel_id) VALUES (?, ?, ?)",
            (discord_thread_id, trello_card_id, discord_channel_id),
        )
        await self._conn.commit()

    async def get_card_id_for_thread(self, discord_thread_id: str) -> str | None:
        cursor = await self._conn.execute(
            "SELECT trello_card_id FROM thread_card_map WHERE discord_thread_id = ?",
            (discord_thread_id,),
        )
        row = await cursor.fetchone()
        return row["trello_card_id"] if row else None

    async def get_thread_id_for_card(self, trello_card_id: str) -> str | None:
        cursor = await self._conn.execute(
            "SELECT discord_thread_id FROM thread_card_map WHERE trello_card_id = ?",
            (trello_card_id,),
        )
        row = await cursor.fetchone()
        return row["discord_thread_id"] if row else None

    async def get_channel_id_for_thread(self, discord_thread_id: str) -> str | None:
        cursor = await self._conn.execute(
            "SELECT discord_channel_id FROM thread_card_map WHERE discord_thread_id = ?",
            (discord_thread_id,),
        )
        row = await cursor.fetchone()
        return row["discord_channel_id"] if row else None

    async def get_all_mappings(self) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT discord_thread_id, trello_card_id, discord_channel_id FROM thread_card_map"
        )
        rows = await cursor.fetchall()
        return [
            {
                "discord_thread_id": row["discord_thread_id"],
                "trello_card_id": row["trello_card_id"],
                "discord_channel_id": row["discord_channel_id"],
            }
            for row in rows
        ]

    async def add_synced_comment(self, source: str, source_id: str, trello_card_id: str, discord_thread_id: str) -> None:
        await self._conn.execute(
            "INSERT INTO synced_comments (source, source_id, trello_card_id, discord_thread_id) VALUES (?, ?, ?, ?)",
            (source, source_id, trello_card_id, discord_thread_id),
        )
        await self._conn.commit()

    async def is_comment_synced(self, source: str, source_id: str) -> bool:
        cursor = await self._conn.execute(
            "SELECT 1 FROM synced_comments WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        return await cursor.fetchone() is not None

    async def get_cached_list_id(self, trello_card_id: str) -> str | None:
        cursor = await self._conn.execute(
            "SELECT list_id FROM card_state_cache WHERE trello_card_id = ?",
            (trello_card_id,),
        )
        row = await cursor.fetchone()
        return row["list_id"] if row else None

    async def update_cached_list_id(self, trello_card_id: str, list_id: str) -> None:
        await self._conn.execute(
            """INSERT INTO card_state_cache (trello_card_id, list_id, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(trello_card_id) DO UPDATE SET list_id = ?, updated_at = CURRENT_TIMESTAMP""",
            (trello_card_id, list_id, list_id),
        )
        await self._conn.commit()

    async def check_health(self) -> bool:
        """Returns True if DB is accessible."""
        try:
            cursor = await self._conn.execute("SELECT 1")
            await cursor.fetchone()
            return True
        except Exception:
            return False
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_database.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add bot/database.py tests/test_database.py
git commit -m "feat: add database module with SQLite schema and helpers"
```

---

### Task 4: Trello Client

**Files:**
- Create: `bot/trello_client.py`
- Create: `tests/test_trello_client.py`

**Step 1: Write the failing tests**

Tests use `httpx`'s built-in mock transport to avoid real API calls.

```python
# tests/test_trello_client.py
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trello_client.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Write implementation**

```python
# bot/trello_client.py
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.trello.com/1"


class TrelloClient:
    def __init__(
        self,
        api_key: str,
        api_token: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_token = api_token
        kwargs: dict[str, Any] = {"timeout": 30.0}
        if transport:
            kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**kwargs)
        self._list_ids: dict[str, str] = {}

    def _params(self, **extra: Any) -> dict[str, Any]:
        return {"key": self._api_key, "token": self._api_token, **extra}

    async def _get(self, path: str, **params: Any) -> Any:
        resp = await self._client.get(f"{BASE_URL}{path}", params=self._params(**params))
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, **params: Any) -> Any:
        resp = await self._client.post(f"{BASE_URL}{path}", params=self._params(**params))
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()

    async def get_lists(self, board_id: str) -> list[dict]:
        return await self._get(f"/boards/{board_id}/lists")

    async def create_card(self, list_id: str, name: str, desc: str) -> dict:
        return await self._post("/cards", idList=list_id, name=name, desc=desc)

    async def get_card(self, card_id: str, fields: str = "idList") -> dict:
        return await self._get(f"/cards/{card_id}", fields=fields)

    async def get_card_actions(self, card_id: str, filter: str = "commentCard") -> list[dict]:
        return await self._get(f"/cards/{card_id}/actions", filter=filter)

    async def add_comment(self, card_id: str, text: str) -> dict:
        return await self._post(f"/cards/{card_id}/actions/comments", text=text)

    async def add_attachment(self, card_id: str, filename: str, data: bytes, mime_type: str) -> dict:
        resp = await self._client.post(
            f"{BASE_URL}/cards/{card_id}/attachments",
            params=self._params(),
            files={"file": (filename, data, mime_type)},
        )
        resp.raise_for_status()
        return resp.json()

    async def resolve_list_ids(self, board_id: str) -> dict[str, str]:
        lists = await self.get_lists(board_id)
        self._list_ids = {lst["name"]: lst["id"] for lst in lists}
        logger.info("Resolved %d Trello lists", len(self._list_ids))
        return self._list_ids

    def get_list_name(self, list_id: str) -> str | None:
        for name, lid in self._list_ids.items():
            if lid == list_id:
                return name
        return None

    async def check_health(self) -> bool:
        """Returns True if Trello API is reachable with valid credentials."""
        try:
            await self._get("/members/me", fields="id")
            return True
        except Exception:
            return False
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_trello_client.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add bot/trello_client.py tests/test_trello_client.py
git commit -m "feat: add Trello API client with httpx"
```

---

### Task 5: Sync Module

**Files:**
- Create: `bot/sync.py`
- Create: `tests/test_sync.py`

**Context:** `sync.py` contains the core bidirectional sync logic. It depends on `Database`, `TrelloClient`, `Config`, and a Discord bot reference. Tests mock all external dependencies.

**Step 1: Write the failing tests**

```python
# tests/test_sync.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
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
    trello.get_list_name = MagicMock(side_effect=lambda lid: {"l1": "To Do", "l2": "In Progress", "l3": "Testing"}.get(lid))
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
        {"discord_thread_id": "t1", "trello_card_id": "c1", "discord_channel_id": "ch1"}
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


@pytest.mark.asyncio
async def test_poll_syncs_new_trello_comment(sync_service, mock_db, mock_trello, mock_bot):
    mock_db.get_all_mappings.return_value = [
        {"discord_thread_id": "t1", "trello_card_id": "c1", "discord_channel_id": "ch1"}
    ]
    mock_trello.get_card.return_value = {"idList": "l1"}
    mock_trello.get_card_actions.return_value = [
        {"id": "action1", "memberCreator": {"fullName": "Alice"}, "data": {"text": "hello from trello"}}
    ]
    mock_db.get_cached_list_id.return_value = "l1"  # No list change
    mock_db.is_comment_synced.return_value = False

    mock_thread = AsyncMock()
    mock_bot.get_channel = MagicMock(return_value=mock_thread)

    await sync_service.poll_trello_changes()

    mock_thread.send.assert_awaited_once()
    sent_text = mock_thread.send.call_args[0][0]
    assert "[Trello]" in sent_text
    assert "Alice" in sent_text
    assert "hello from trello" in sent_text
    mock_db.add_synced_comment.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_skips_already_synced_comment(sync_service, mock_db, mock_trello, mock_bot):
    mock_db.get_all_mappings.return_value = [
        {"discord_thread_id": "t1", "trello_card_id": "c1", "discord_channel_id": "ch1"}
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sync.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Write implementation**

```python
# bot/sync.py
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord
    from bot.config import Config
    from bot.database import Database
    from bot.trello_client import TrelloClient

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(
        self,
        db: Database,
        trello: TrelloClient,
        bot: discord.Client,
        config: Config,
    ) -> None:
        self.db = db
        self.trello = trello
        self.bot = bot
        self.config = config

    async def poll_trello_changes(self) -> None:
        mappings = await self.db.get_all_mappings()
        if not mappings:
            return

        for mapping in mappings:
            try:
                await self._process_card(mapping)
            except Exception as e:
                logger.error(
                    "Error processing card %s: %s",
                    mapping["trello_card_id"],
                    e,
                )
            await asyncio.sleep(0.1)

    async def _process_card(self, mapping: dict) -> None:
        card_id = mapping["trello_card_id"]
        thread_id = mapping["discord_thread_id"]

        try:
            card = await self.trello.get_card(card_id)
        except Exception as e:
            logger.warning("Could not fetch card %s (maybe deleted): %s", card_id, e)
            return

        # Check for list change
        current_list_id = card["idList"]
        cached_list_id = await self.db.get_cached_list_id(card_id)

        if cached_list_id and current_list_id != cached_list_id:
            await self._handle_card_moved(thread_id, current_list_id)
            await self.db.update_cached_list_id(card_id, current_list_id)
        elif not cached_list_id:
            await self.db.update_cached_list_id(card_id, current_list_id)

        # Check for new comments
        actions = await self.trello.get_card_actions(card_id)
        for action in actions:
            action_id = action["id"]
            if await self.db.is_comment_synced("trello", action_id):
                continue

            author = action.get("memberCreator", {}).get("fullName", "Unknown")
            text = action.get("data", {}).get("text", "")
            prefix = self.config.bot_comment_prefix

            thread = self.bot.get_channel(int(thread_id))
            if thread is None:
                logger.warning("Discord thread %s not found", thread_id)
                continue

            await thread.send(f"{prefix} {author}: {text}")
            await self.db.add_synced_comment("trello", action_id, card_id, thread_id)

    async def _handle_card_moved(self, thread_id: str, new_list_id: str) -> None:
        list_name = self.trello.get_list_name(new_list_id)
        if list_name is None:
            logger.warning("Unknown list ID: %s", new_list_id)
            return

        tag_name = self.config.list_to_tag_map.get(list_name)
        managed_names = set(self.config.managed_tag_names)

        thread = self.bot.get_channel(int(thread_id))
        if thread is None:
            logger.warning("Discord thread %s not found for tag update", thread_id)
            return

        channel = thread.parent
        if channel is None:
            logger.warning("Could not find parent channel for thread %s", thread_id)
            return

        available_tags = {t.name: t for t in channel.available_tags}

        # Keep non-managed tags
        new_tags = [t for t in thread.applied_tags if t.name not in managed_names]

        # Add the target tag if applicable
        if tag_name and tag_name in available_tags:
            new_tags.append(available_tags[tag_name])
        elif tag_name:
            logger.warning("Tag '%s' not found on channel, skipping", tag_name)

        await thread.edit(applied_tags=new_tags)
        logger.info("Updated thread %s tags for list '%s'", thread_id, list_name)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sync.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add bot/sync.py tests/test_sync.py
git commit -m "feat: add sync module with bidirectional comment and tag sync"
```

---

### Task 6: Discord Event Handlers

**Files:**
- Create: `bot/discord_handler.py`
- Create: `tests/test_discord_handler.py`

**Step 1: Write the failing tests**

```python
# tests/test_discord_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from bot.discord_handler import handle_thread_create, handle_message
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
    trello._list_ids = {"To Do": "l1"}
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
    # Starter message has different ID
    type(message.channel).id.__get__ = lambda self, obj, objtype=None: 555

    mock_db.get_card_id_for_thread.return_value = "card1"
    mock_db.is_comment_synced.return_value = False

    bot_user = MagicMock()
    bot_user.id = 1

    await handle_message(message, mock_db, mock_trello, config, bot_user)

    mock_trello.add_comment.assert_awaited_once()
    comment_text = mock_trello.add_comment.call_args[0][1]
    assert "User1" in comment_text
    assert "A reply" in comment_text
    mock_db.add_synced_comment.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_message_ignores_bot(mock_db, mock_trello, config):
    message = MagicMock()
    message.author.bot = True

    bot_user = MagicMock()
    await handle_message(message, mock_db, mock_trello, config, bot_user)

    mock_db.get_card_id_for_thread.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_message_ignores_untracked_thread(mock_db, mock_trello, config):
    message = MagicMock()
    message.author.bot = False
    message.channel.id = 555

    mock_db.get_card_id_for_thread.return_value = None

    bot_user = MagicMock()
    await handle_message(message, mock_db, mock_trello, config, bot_user)

    mock_trello.add_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_message_skips_starter_message(mock_db, mock_trello, config):
    """The starter message ID equals the thread ID — it should be skipped."""
    message = MagicMock()
    message.author.bot = False
    message.channel.id = 555
    message.id = 555  # Same as thread/channel ID = starter message

    mock_db.get_card_id_for_thread.return_value = "card1"

    bot_user = MagicMock()
    await handle_message(message, mock_db, mock_trello, config, bot_user)

    mock_trello.add_comment.assert_not_awaited()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_discord_handler.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Write implementation**

```python
# bot/discord_handler.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot.config import Config
    from bot.database import Database
    from bot.trello_client import TrelloClient

logger = logging.getLogger(__name__)


async def handle_thread_create(
    thread: discord.Thread,
    db: Database,
    trello: TrelloClient,
    config: Config,
) -> None:
    if thread.parent_id not in config.discord_forum_channel_ids:
        return

    try:
        starter = await thread.fetch_message(thread.id)
    except discord.NotFound:
        logger.warning("Could not fetch starter message for thread %s", thread.id)
        return

    desc = starter.content or ""
    desc += f"\n\n---\n[Discord Thread]({thread.jump_url})"

    # Handle attachments
    oversized: list[str] = []
    attachment_data: list[tuple[str, bytes, str]] = []

    for att in starter.attachments:
        if att.size > config.max_attachment_size_mb * 1024 * 1024:
            oversized.append(f"- [{att.filename}]({att.url}) (too large: {att.size // 1024 // 1024}MB)")
        else:
            data = await att.read()
            attachment_data.append((att.filename, data, att.content_type or "application/octet-stream"))

    if oversized:
        desc += "\n\n**Attachments too large to upload:**\n" + "\n".join(oversized)

    # Get the To Do list ID
    list_id = trello._list_ids.get(config.trello_list_todo)
    if not list_id:
        logger.error("Could not find Trello list '%s'", config.trello_list_todo)
        return

    try:
        card = await trello.create_card(list_id, thread.name, desc)
    except Exception as e:
        logger.error("Failed to create Trello card for thread %s: %s", thread.id, e)
        return

    card_id = card["id"]

    # Upload attachments
    for filename, data, mime_type in attachment_data:
        try:
            await trello.add_attachment(card_id, filename, data, mime_type)
        except Exception as e:
            logger.error("Failed to upload attachment %s to card %s: %s", filename, card_id, e)

    await db.add_mapping(str(thread.id), card_id, str(thread.parent_id))
    await db.update_cached_list_id(card_id, card["idList"])
    logger.info("Created Trello card %s for thread %s", card_id, thread.id)


async def handle_message(
    message: discord.Message,
    db: Database,
    trello: TrelloClient,
    config: Config,
    bot_user: discord.User,
) -> None:
    if message.author.bot:
        return

    thread_id = str(message.channel.id)
    card_id = await db.get_card_id_for_thread(thread_id)
    if not card_id:
        return

    # Skip the starter message (its ID equals the thread ID)
    if message.id == message.channel.id:
        return

    if await db.is_comment_synced("discord", str(message.id)):
        return

    text = f"**{message.author.display_name}:** {message.content}"

    # Append attachment URLs
    if message.attachments:
        urls = "\n".join(f"- {att.url}" for att in message.attachments)
        text += f"\n\n**Attachments:**\n{urls}"

    try:
        await trello.add_comment(card_id, text)
    except Exception as e:
        logger.error("Failed to sync message %s to Trello: %s", message.id, e)
        return

    await db.add_synced_comment("discord", str(message.id), card_id, thread_id)
    logger.info("Synced Discord message %s to Trello card %s", message.id, card_id)


def setup_handlers(
    bot: discord.Client,
    db: Database,
    trello: TrelloClient,
    config: Config,
) -> None:
    """Register Discord event handlers on the bot."""

    @bot.event
    async def on_thread_create(thread: discord.Thread) -> None:
        await handle_thread_create(thread, db, trello, config)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        await handle_message(message, db, trello, config, bot.user)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_discord_handler.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add bot/discord_handler.py tests/test_discord_handler.py
git commit -m "feat: add Discord event handlers for thread create and message sync"
```

---

### Task 7: Poller

**Files:**
- Create: `bot/poller.py`
- Create: `tests/test_poller.py`

**Step 1: Write the failing test**

```python
# tests/test_poller.py
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from bot.poller import start_poller


@pytest.mark.asyncio
async def test_poller_calls_poll(monkeypatch):
    sync_service = AsyncMock()
    sync_service.poll_trello_changes = AsyncMock()

    # Patch asyncio.sleep to break out of the loop after one iteration
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_poller.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Write implementation**

```python
# bot/poller.py
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.sync import SyncService

logger = logging.getLogger(__name__)


async def _poll_loop(sync_service: SyncService, poll_interval: int) -> None:
    while True:
        try:
            await sync_service.poll_trello_changes()
        except Exception as e:
            logger.error("Poller error: %s", e)
        await asyncio.sleep(poll_interval)


def start_poller(sync_service: SyncService, poll_interval: int = 30) -> asyncio.Task:
    logger.info("Starting Trello poller (interval: %ds)", poll_interval)
    return asyncio.create_task(_poll_loop(sync_service, poll_interval))
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_poller.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add bot/poller.py tests/test_poller.py
git commit -m "feat: add Trello poller background task"
```

---

### Task 8: Health Check Server

**Files:**
- Create: `bot/health.py`
- Create: `tests/test_health.py`

**Step 1: Write the failing test**

```python
# tests/test_health.py
import pytest
from unittest.mock import AsyncMock
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from bot.health import create_health_app


@pytest.mark.asyncio
async def test_health_healthy():
    db = AsyncMock()
    db.check_health = AsyncMock(return_value=True)
    trello = AsyncMock()
    trello.check_health = AsyncMock(return_value=True)

    app = create_health_app(db, trello)

    from aiohttp.test_utils import TestClient, TestServer

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

    from aiohttp.test_utils import TestClient, TestServer

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

    from aiohttp.test_utils import TestClient, TestServer

    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 503
        data = await resp.json()
        assert data["details"]["trello"] is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Write implementation**

```python
# bot/health.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from bot.database import Database
    from bot.trello_client import TrelloClient

logger = logging.getLogger(__name__)


def create_health_app(db: Database, trello: TrelloClient) -> web.Application:
    async def health_handler(request: web.Request) -> web.Response:
        db_ok = await db.check_health()
        trello_ok = await trello.check_health()

        if db_ok and trello_ok:
            return web.json_response({"status": "healthy"})

        return web.json_response(
            {
                "status": "unhealthy",
                "details": {
                    "database": db_ok,
                    "trello": trello_ok,
                },
            },
            status=503,
        )

    app = web.Application()
    app.router.add_get("/health", health_handler)
    return app
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_health.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add bot/health.py tests/test_health.py
git commit -m "feat: add smart health check endpoint"
```

---

### Task 9: Main Entry Point

**Files:**
- Create: `bot/main.py`

**Note:** This is the integration glue — it wires everything together. It's not unit tested directly because it depends on real Discord/Trello connections. We verify it imports correctly.

**Step 1: Write implementation**

```python
# bot/main.py
from __future__ import annotations

import asyncio
import logging
import os

import discord
from aiohttp import web
from dotenv import load_dotenv

from bot.config import Config
from bot.database import Database
from bot.discord_handler import setup_handlers
from bot.health import create_health_app
from bot.poller import start_poller
from bot.sync import SyncService
from bot.trello_client import TrelloClient

logger = logging.getLogger(__name__)


async def run_health_server(app: web.Application, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health check server listening on port %d", port)
    return runner


def main() -> None:
    load_dotenv()

    config = Config.from_env()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True

    bot = discord.Client(intents=intents)
    db = Database(config.db_path)
    trello = TrelloClient(api_key=config.trello_api_key, api_token=config.trello_api_token)

    health_runner: web.AppRunner | None = None

    @bot.event
    async def on_ready() -> None:
        nonlocal health_runner
        logger.info("Bot logged in as %s", bot.user)

        await db.init()
        await trello.resolve_list_ids(config.trello_board_id)

        sync_service = SyncService(db, trello, bot, config)
        setup_handlers(bot, db, trello, config)

        start_poller(sync_service, config.trello_poll_interval_seconds)

        health_app = create_health_app(db, trello)
        health_runner = await run_health_server(health_app, config.health_port)

        logger.info("Bot is ready. Watching %d forum channel(s).", len(config.discord_forum_channel_ids))

    try:
        bot.run(config.discord_bot_token, log_handler=None)
    finally:
        logger.info("Bot shutting down")


if __name__ == "__main__":
    main()
```

**Step 2: Verify it imports correctly**

Run: `python -c "from bot.main import main; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add bot/main.py
git commit -m "feat: add main entry point wiring all components together"
```

---

### Task 10: Integration Verification

**Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (22 tests total)

**Step 2: Verify Docker build**

Run: `docker build -t trellobot .`
Expected: Build succeeds

**Step 3: Commit any remaining files**

```bash
git status
# If anything is missing, add and commit
```

**Step 4: Final commit with all passing tests**

```bash
git add -A
git commit -m "chore: verify full test suite and Docker build"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Project scaffolding | - |
| 2 | Config module | 3 |
| 3 | Database module | 5 |
| 4 | Trello client | 7 |
| 5 | Sync module | 4 |
| 6 | Discord handlers | 6 |
| 7 | Poller | 1 |
| 8 | Health check | 3 |
| 9 | Main entry point | import check |
| 10 | Integration verification | full suite run |

**Total: 10 tasks, ~29 tests**
