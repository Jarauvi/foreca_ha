"""Deterministic fake aiohttp session/response objects for tests.

The coordinator uses ``async_get_clientsession(hass).get(url, headers, timeout)``
as an async context manager and then inspects ``response.status`` and awaits
``response.text()``, ``response.read()`` or ``response.json()``.

These fakes avoid relying on library-level mocking packages (``aioresponses``)
whose compatibility with newer ``aiohttp`` releases can drift.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional, Pattern, Union


class FakeResponse:
    """Mimic the subset of aiohttp.ClientResponse used by the coordinator."""

    def __init__(
        self,
        status: int = 200,
        body: bytes = b"",
        payload: Optional[dict] = None,
        content_type: str = "application/octet-stream",
    ):
        self.status = status
        self.content_type = content_type
        if payload is not None:
            self._body: bytes = json.dumps(payload).encode("utf-8")
        elif isinstance(body, str):
            self._body = body.encode("utf-8")
        else:
            self._body = body

    async def text(self) -> str:
        """Return the body decoded as UTF-8 text."""
        return self._body.decode("utf-8")

    async def read(self) -> bytes:
        """Return the raw body bytes."""
        return self._body

    async def json(self) -> dict:
        """Return the body parsed as JSON."""
        return json.loads(self._body.decode("utf-8"))

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakeSession:
    """Mimic the subset of aiohttp.ClientSession used by the coordinator.

    Register responses by either an exact URL string or a compiled regex
    pattern. Matching is attempted in registration order; the first match for
    the requested URL is returned.
    """

    def __init__(self) -> None:
        self._routes: list[tuple[Union[str, Pattern[str]], FakeResponse]] = []

    def get(
        self,
        url: str,
        *,
        headers: Optional[dict] = None,
        timeout: Optional[Any] = None,
    ) -> FakeResponse:
        """Return a fake response for the requested URL."""
        for route_url, response in self._routes:
            if isinstance(route_url, Pattern):
                if route_url.search(url):
                    return response
            elif route_url == url:
                return response
        raise AssertionError(f"No mocked route for GET {url}")

    def add(
        self,
        url: Union[str, Pattern[str]],
        status: int = 200,
        body: Union[bytes, str] = b"",
        payload: Optional[dict] = None,
    ) -> None:
        """Register a response for a URL or pattern."""
        self._routes.append((url, FakeResponse(status, body, payload)))

