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
