"""Bifrost AI gateway client.

Bifrost here means the open-source gateway from Maxim AI (github.com/maximhq/bifrost): a self-hosted
service that exposes one OpenAI-compatible API (POST /v1/chat/completions, GET /v1/models, GET /health)
in front of many providers. Model names use the "provider/model" form. Bifrost does NOT supply free
tokens: the provider key (e.g. Groq, Gemini, OpenRouter) is configured inside Bifrost itself.

This is the only module in the backend that knows how LLM requests are sent. Agents just call chat().
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..config import Settings
from ..exceptions import (ExternalServiceError, ServiceNotConfigured, UpstreamAuthError, UpstreamQuotaError)
from ..utils.validation import sanitize_text
from .http_client import HttpxTransport, TransportError, TransportTimeout

logger = logging.getLogger("velqora.bifrost")

_RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass
class LLMResult:
    text: str
    model: str
    finish_reason: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


class BifrostService:
    def __init__(self, settings: Settings, transport=None, sleep=asyncio.sleep):
        self.settings = settings
        self.transport = transport or HttpxTransport()
        self._sleep = sleep

    @property
    def configured(self) -> bool:
        return self.settings.bifrost_configured

    # ------------------------------------------------------------------ urls / headers
    def _root(self) -> str:
        base = self.settings.bifrost_base_url
        return base[:-3] if base.endswith("/v1") else base

    def _v1(self, path: str) -> str:
        return f"{self._root()}/v1{path}"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        key = self.settings.bifrost_api_key
        if key:
            if self.settings.bifrost_auth_mode == "virtual_key":
                headers["x-bf-vk"] = key
            else:
                headers["Authorization"] = f"Bearer {key}"
        return headers

    # ------------------------------------------------------------------ chat
    async def chat(self, messages: List[Dict[str, str]], *, max_tokens: Optional[int] = None,
                   temperature: Optional[float] = None, json_mode: Optional[bool] = None,
                   model: Optional[str] = None) -> LLMResult:
        if not self.configured:
            raise ServiceNotConfigured(
                "The AI gateway is not configured. Set BIFROST_BASE_URL and BIFROST_MODEL in backend/.env.",
                code="bifrost_not_configured")
        primary = model or self.settings.bifrost_model
        fallback = self.settings.bifrost_fallback_model if not model else None

        # Try primary, then fallback (if set) on capacity/availability errors
        last_exc: Optional[Exception] = None
        for chosen, is_fallback in ((primary, False), (fallback, True)):
            if not chosen:
                continue
            try:
                return await self._chat_with_model(
                    chosen, messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    json_mode=json_mode,
                )
            except (UpstreamQuotaError, ExternalServiceError) as exc:
                last_exc = exc
                # Only cascade to fallback for capacity / availability errors
                if is_fallback or not fallback or exc.code not in (
                        "bifrost_rate_limited", "bifrost_error", "bifrost_unreachable",
                        "upstream_quota_exceeded"):
                    raise
                logger.warning(
                    "Primary model %s failed (%s); trying fallback %s", chosen, exc.code, fallback
                )
        # Both primary and fallback exhausted
        if last_exc:
            raise last_exc  # type: ignore[misc]
        raise ExternalServiceError("No model could serve the request.", code="bifrost_error")

    async def _chat_with_model(
        self,
        chosen: str,
        messages: List[Dict[str, str]],
        *,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        json_mode: Optional[bool] = None,
    ) -> LLMResult:
        body: Dict[str, Any] = {
            "model": chosen,
            "messages": messages,
            "max_tokens": max_tokens or self.settings.bifrost_max_tokens,
            "temperature": self.settings.bifrost_temperature if temperature is None else temperature,
            "stream": False,
        }
        if self.settings.bifrost_json_mode if json_mode is None else json_mode:
            body["response_format"] = {"type": "json_object"}
        resp = await self._request("POST", self._v1("/chat/completions"), body)
        try:
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ExternalServiceError(
                "The AI gateway returned an unexpected response.", code="bifrost_bad_response"
            )
        if isinstance(content, list):      # some providers return content as a list of parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not content or not str(content).strip():
            raise ExternalServiceError(
                "The AI model returned an empty response.", code="bifrost_empty_response"
            )
        usage = data.get("usage") or {}
        return LLMResult(
            text=str(content),
            model=str(data.get("model") or chosen),
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

    async def _request(self, method: str, url: str, body: Optional[dict] = None):
        attempts = self.settings.bifrost_max_retries + 1
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                resp = await self.transport.request(method, url, headers=self._headers(), json=body,
                                                    timeout=self.settings.bifrost_timeout)
            except TransportTimeout as exc:
                last_error = exc
                logger.warning("Bifrost timeout (attempt %d/%d)", attempt + 1, attempts)
            except TransportError as exc:
                last_error = exc
                logger.warning("Bifrost network error %s (attempt %d/%d)", exc, attempt + 1, attempts)
            else:
                status = resp.status_code
                if 200 <= status < 300:
                    return resp
                detail = self._error_detail(resp)
                if status in (401, 403):
                    raise UpstreamAuthError(
                        "The AI gateway rejected the credentials. Check BIFROST_API_KEY / the provider key in Bifrost.",
                        code="bifrost_auth_failed")
                if status in _RETRY_STATUS and attempt < attempts - 1:
                    delay = self._delay(resp.headers.get("retry-after"), attempt)
                    logger.warning("Bifrost HTTP %s; retrying in %.1fs", status, delay)
                    await self._sleep(delay)
                    continue
                if status == 429:
                    raise UpstreamQuotaError("The AI model rate limit or free-tier quota was reached.",
                                             code="bifrost_rate_limited")
                if status in (400, 404, 422):
                    raise ExternalServiceError(
                        f"The AI gateway rejected the request{': ' + detail if detail else ''}. "
                        "Check BIFROST_MODEL (format provider/model) and that the provider is configured in Bifrost.",
                        code="bifrost_bad_request")
                raise ExternalServiceError(f"The AI gateway failed (HTTP {status}).", code="bifrost_error")
            if attempt < attempts - 1:
                await self._sleep(self._delay(None, attempt))
        raise ExternalServiceError("Could not reach the AI gateway. Is Bifrost running at BIFROST_BASE_URL?",
                                   code="bifrost_unreachable") from last_error

    @staticmethod
    def _error_detail(resp) -> str:
        try:
            data = resp.json()
            err = data.get("error") if isinstance(data, dict) else None
            msg = err.get("message") if isinstance(err, dict) else (err if isinstance(err, str) else None)
            return sanitize_text(msg, 160) if msg else ""
        except (ValueError, AttributeError):
            return ""

    @staticmethod
    def _delay(retry_after: Optional[str], attempt: int) -> float:
        if retry_after:
            try:
                return max(0.5, min(float(retry_after), 20.0))
            except ValueError:
                pass
        return min(1.5 * (2 ** attempt), 12.0)

    # ------------------------------------------------------------------ health
    async def health(self, deep: bool = False) -> dict:
        info: Dict[str, Any] = {"configured": self.configured, "base_url_set": bool(self.settings.bifrost_base_url),
                                "model": self.settings.bifrost_model or None,
                                "api_key_set": bool(self.settings.bifrost_api_key)}
        if not self.settings.bifrost_base_url:
            info.update(reachable=False, status="not_configured", detail="Set BIFROST_BASE_URL in backend/.env")
            return info
        try:
            resp = await self.transport.request("GET", f"{self._root()}/health", headers=self._headers(), timeout=8)
        except TransportTimeout:
            info.update(reachable=False, status="timeout", detail="Gateway timed out")
            return info
        except TransportError:
            info.update(reachable=False, status="unreachable",
                        detail="Cannot reach Bifrost. Start it (npx -y @maximhq/bifrost) and check BIFROST_BASE_URL.")
            return info
        if resp.status_code >= 400:
            info.update(reachable=True, status="error", detail=f"Gateway health returned HTTP {resp.status_code}")
            return info
        info.update(reachable=True, status="ok")
        if not self.settings.bifrost_model:
            info.update(status="not_configured", detail="Set BIFROST_MODEL (format provider/model)")
            return info
        try:
            models = await self.transport.request("GET", self._v1("/models"), headers=self._headers(), timeout=10)
            if models.status_code == 200:
                ids = [m.get("id") for m in (models.json() or {}).get("data", []) if isinstance(m, dict)]
                info["model_listed"] = self.settings.bifrost_model in ids if ids else None
        except (TransportError, ValueError):
            info["model_listed"] = None
        if deep:
            try:
                result = await self.chat([{"role": "user", "content": "Reply with the single word OK."}],
                                         max_tokens=8, temperature=0, json_mode=False)
                info.update(generation="ok", model_response_chars=len(result.text))
            except ExternalServiceError as exc:
                info.update(status="degraded", generation="failed", detail=exc.message)
            except ServiceNotConfigured as exc:
                info.update(status="not_configured", detail=exc.message)
        return info

    async def aclose(self) -> None:
        close = getattr(self.transport, "aclose", None)
        if close:
            await close()
