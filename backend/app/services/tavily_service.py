"""Tavily web-search client (REST API, https://docs.tavily.com).

Credit-conscious by design: in-process result cache, per-day call cap, no raw-content / answer / image
options, basic search depth by default (1 credit per request).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date
from typing import Any, Dict, List, Optional

from ..config import Settings
from ..exceptions import (ExternalServiceError, ServiceNotConfigured, UpstreamAuthError, UpstreamQuotaError)
from ..utils.date_utils import today_utc
from .http_client import HttpxTransport, TransportError, TransportTimeout

logger = logging.getLogger("velqora.tavily")

_RETRY_STATUS = {429, 500, 502, 503, 504}


class TavilyService:
    def __init__(self, settings: Settings, transport=None, sleep=asyncio.sleep, clock=time.monotonic):
        self.settings = settings
        self.transport = transport or HttpxTransport()
        self._sleep = sleep
        self._clock = clock
        self._cache: Dict[str, tuple] = {}
        self._calls_day: date = today_utc()
        self._calls_today = 0
        self._credits_today = 0

    # ------------------------------------------------------------------ state
    @property
    def configured(self) -> bool:
        return self.settings.tavily_configured

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.tavily_api_key}", "Content-Type": "application/json",
                "Accept": "application/json"}

    def _roll_day(self) -> None:
        today = today_utc()
        if today != self._calls_day:
            self._calls_day, self._calls_today, self._credits_today = today, 0, 0

    def stats(self) -> dict:
        self._roll_day()
        return {"calls_today": self._calls_today, "estimated_credits_today": self._credits_today,
                "daily_call_cap": self.settings.tavily_daily_call_cap}

    # ------------------------------------------------------------------ search
    async def search(self, query: str, *, topic: str = "general", start_date: Optional[str] = None,
                     end_date: Optional[str] = None, max_results: int = 5, search_depth: Optional[str] = None,
                     include_domains: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.configured:
            raise ServiceNotConfigured("Tavily is not configured. Set TAVILY_API_KEY in backend/.env.",
                                       code="tavily_not_configured")
        body: Dict[str, Any] = {
            "query": query[:400], "topic": topic, "search_depth": search_depth or self.settings.tavily_search_depth,
            "max_results": max(1, min(int(max_results), 20)), "include_answer": False,
            "include_raw_content": False, "include_images": False,
        }
        if start_date:
            body["start_date"] = start_date
        if end_date:
            body["end_date"] = end_date
        if include_domains:
            body["include_domains"] = include_domains[:5]

        cache_key = json.dumps(body, sort_keys=True)
        cached = self._cache.get(cache_key)
        ttl = self.settings.tavily_cache_ttl
        if cached and ttl and self._clock() - cached[0] < ttl:
            logger.info("Tavily cache hit (no credit used)")
            return cached[1]

        self._roll_day()
        if self._calls_today >= self.settings.tavily_daily_call_cap:
            raise UpstreamQuotaError("Daily Tavily call cap reached. Raise TAVILY_DAILY_CALL_CAP or try tomorrow.",
                                     code="tavily_daily_cap")
        data = await self._post("/search", body)
        self._calls_today += 1
        self._credits_today += 2 if body["search_depth"] == "advanced" else 1
        if ttl:
            self._cache[cache_key] = (self._clock(), data)
            if len(self._cache) > 300:
                self._cache.pop(next(iter(self._cache)))
        return data

    async def _post(self, path: str, body: dict) -> dict:
        resp = await self._request("POST", path, body)
        try:
            data = resp.json()
        except ValueError:
            raise ExternalServiceError("Tavily returned an unreadable response.", code="tavily_bad_response")
        if not isinstance(data, dict):
            raise ExternalServiceError("Tavily returned an unexpected response.", code="tavily_bad_response")
        return data

    async def _request(self, method: str, path: str, body: Optional[dict] = None):
        url = self.settings.tavily_base_url + path
        attempts = self.settings.tavily_max_retries + 1
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                resp = await self.transport.request(method, url, headers=self._headers(), json=body,
                                                    timeout=self.settings.tavily_timeout)
            except TransportTimeout as exc:
                last_error = exc
                logger.warning("Tavily timeout (attempt %d/%d)", attempt + 1, attempts)
            except TransportError as exc:
                last_error = exc
                logger.warning("Tavily network error %s (attempt %d/%d)", exc, attempt + 1, attempts)
            else:
                status = resp.status_code
                if 200 <= status < 300:
                    return resp
                if status in (401, 403):
                    raise UpstreamAuthError("Tavily rejected the API key. Check TAVILY_API_KEY.",
                                            code="tavily_auth_failed")
                if status in (432, 433):
                    raise UpstreamQuotaError("Tavily plan or credit limit reached.", code="tavily_quota_exceeded")
                if status in _RETRY_STATUS and attempt < attempts - 1:
                    delay = self._retry_delay(resp.headers.get("retry-after"), attempt)
                    logger.warning("Tavily HTTP %s; retrying in %.1fs", status, delay)
                    await self._sleep(delay)
                    continue
                if status == 429:
                    raise UpstreamQuotaError("Tavily rate limit hit. Please retry shortly.", code="tavily_rate_limited")
                if status == 400:
                    raise ExternalServiceError("Tavily rejected the search request.", code="tavily_bad_request")
                raise ExternalServiceError(f"Tavily request failed (HTTP {status}).", code="tavily_error")
            if attempt < attempts - 1:
                await self._sleep(self._retry_delay(None, attempt))
        raise ExternalServiceError("Could not reach Tavily. Check your connection and try again.",
                                   code="tavily_unreachable") from last_error

    @staticmethod
    def _retry_delay(retry_after: Optional[str], attempt: int) -> float:
        if retry_after:
            try:
                return max(0.5, min(float(retry_after), 20.0))
            except ValueError:
                pass
        return min(0.8 * (2 ** attempt), 8.0)

    # ------------------------------------------------------------------ health
    async def health(self) -> dict:
        """Connectivity check via GET /usage, which does not consume search credits."""
        if not self.configured:
            return {"configured": False, "reachable": False, "status": "not_configured",
                    "detail": "Set TAVILY_API_KEY in backend/.env"}
        try:
            resp = await self.transport.request("GET", self.settings.tavily_base_url + "/usage",
                                                headers=self._headers(), timeout=min(self.settings.tavily_timeout, 10))
        except TransportTimeout:
            return {"configured": True, "reachable": False, "status": "timeout", "detail": "Tavily timed out"}
        except TransportError:
            return {"configured": True, "reachable": False, "status": "unreachable", "detail": "Network error"}
        if resp.status_code in (401, 403):
            return {"configured": True, "reachable": True, "status": "auth_failed", "detail": "API key rejected"}
        if resp.status_code != 200:
            return {"configured": True, "reachable": True, "status": "error", "detail": f"HTTP {resp.status_code}"}
        info: Dict[str, Any] = {"configured": True, "reachable": True, "status": "ok", "local": self.stats()}
        try:
            key = (resp.json() or {}).get("key") or {}
            if key.get("usage") is not None:
                info["credits_used"] = key.get("usage")
                info["credit_limit"] = key.get("limit")
        except ValueError:
            pass
        return info

    async def aclose(self) -> None:
        close = getattr(self.transport, "aclose", None)
        if close:
            await close()
