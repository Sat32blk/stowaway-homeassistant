"""Small client for Stowaway's /_stowaway/api/v1 endpoints."""
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import aiohttp


class StowawayError(Exception):
    """Something went wrong talking to Stowaway."""


class CannotConnect(StowawayError):
    """Stowaway didn't answer."""


class InvalidAuth(StowawayError):
    """The API token was refused."""


def normalize_url(url: str) -> str:
    """'192.168.1.2:8880', 'http://nas:8880/_stowaway/' -> 'http://192.168.1.2:8880'."""
    url = url.strip().rstrip("/")
    if "://" not in url:
        url = "http://" + url
    if url.endswith("/_stowaway"):
        url = url[: -len("/_stowaway")]
    return url.rstrip("/")


class StowawayClient:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self.base = normalize_url(url)
        self._token = token

    @property
    def api(self) -> str:
        return f"{self.base}/_stowaway/api/v1"

    async def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with asyncio.timeout(20):
                resp = await self._session.request(method, self.api + path, json=body, headers=headers)
                if resp.status == 401:
                    raise InvalidAuth("the API token was refused")
                if resp.status == 403:
                    text = await resp.text()
                    raise InvalidAuth(f"access refused: {text[:200]}")
                if resp.status >= 400:
                    try:
                        detail = (await resp.json()).get("detail")
                    except (aiohttp.ContentTypeError, ValueError):
                        detail = await resp.text()
                    raise StowawayError(f"Stowaway answered {resp.status}: {detail}")
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(f"can't reach Stowaway at {self.base}: {err}") from err

    async def info(self) -> dict:
        return await self._request("GET", "/info")

    async def apps(self) -> list[dict]:
        return (await self._request("GET", "/apps"))["apps"]

    async def wake(self, name: str) -> dict:
        return await self._request("POST", f"/apps/{quote(name, safe='')}/wake")

    async def sleep(self, name: str, block: bool | None = None) -> dict:
        return await self._request("POST", f"/apps/{quote(name, safe='')}/sleep", {"block": block})

    async def block(self, name: str, on: bool) -> dict:
        return await self._request("POST", f"/apps/{quote(name, safe='')}/block", {"on": on})

    async def keep_awake(self, name: str, minutes: float | None = None, forever: bool = False) -> dict:
        return await self._request("POST", f"/apps/{quote(name, safe='')}/keep-awake", {"minutes": minutes, "forever": forever})

    async def restart(self, name: str) -> dict:
        return await self._request("POST", f"/apps/{quote(name, safe='')}/restart")
