"""Minimal HTTP transport abstraction.

Services depend on this tiny interface instead of httpx directly, so the HTTP library can be swapped
or faked in tests. ``httpx`` is imported lazily, only when the real transport is first used.
"""
from __future__ import annotations

import json as _json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class TransportError(Exception):
    """Network-level failure (DNS, connection reset, TLS, ...)."""


class TransportTimeout(TransportError):
    """Request exceeded its timeout."""


@dataclass
class HttpResponse:
    status_code: int
    text: str = ""
    headers: Dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return _json.loads(self.text) if self.text else None


class HttpxTransport:
    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            import httpx  # lazy: keeps modules importable without the dependency installed
            self._client = httpx.AsyncClient(follow_redirects=False, limits=httpx.Limits(max_connections=20))
        return self._client

    async def request(self, method: str, url: str, *, headers: Optional[Dict[str, str]] = None,
                      json: Any = None, params: Optional[Dict[str, Any]] = None, timeout: float = 20.0) -> HttpResponse:
        import httpx
        try:
            resp = await self._get_client().request(method, url, headers=headers, json=json, params=params,
                                                    timeout=timeout)
        except httpx.TimeoutException as exc:
            raise TransportTimeout(f"timeout after {timeout}s") from exc
        except httpx.HTTPError as exc:
            raise TransportError(type(exc).__name__) from exc
        return HttpResponse(resp.status_code, resp.text, {k.lower(): v for k, v in resp.headers.items()})

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
