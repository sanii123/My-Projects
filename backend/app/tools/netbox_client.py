"""Thin async client for NetBox's REST API. docs/architecture.md section 4.6.

Every adapter in read_tools.py / write_tools.py goes through this rather than
calling httpx directly - auth, timeout, and error typing live in one place,
so swapping NetBox for another IPAM backend later means writing one new
client with the same method names, not rewriting every adapter.
"""

from typing import Any

import httpx

from app.core.config import settings


class NetBoxUnavailableError(Exception):
    """The NetBox API timed out or returned a 5xx - a backend outage, not a
    "no such subnet." Section 6: the model needs to be able to tell those apart.
    """


class NetBoxNotFoundError(Exception):
    """NetBox returned 404 - the requested object genuinely doesn't exist."""


class NetBoxClient:
    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or settings.netbox_url).rstrip("/")
        self.token = token or settings.netbox_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self.token}", "Accept": "application/json"}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, json=json)

    async def patch(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str) -> None:
        await self._request("DELETE", path)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.HTTPError as exc:
            raise NetBoxUnavailableError(f"NetBox request failed: {exc}") from exc

        if resp.status_code == 404:
            raise NetBoxNotFoundError(f"{method} {path} -> 404")
        if resp.status_code >= 500:
            raise NetBoxUnavailableError(f"{method} {path} -> {resp.status_code}")
        resp.raise_for_status()
        return resp.json() if resp.content else None


netbox = NetBoxClient()
