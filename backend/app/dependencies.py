"""Dependency container, rate limiting and authentication dependencies."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

from fastapi import Depends, Request

from .config import Settings
from .database.connection import Database
from .database.models import SCHEMA_SQL, BriefingRepository, PresentationRepository, ResearchRepository, UserRepository
from .exceptions import AuthError, RateLimitedError
from .security import decode_token
from .services.bifrost_service import BifrostService
from .services.briefing_service import BriefingService
from .services.presentation_ai_service import PresentationAIService
from .services.research_service import ResearchService
from .services.tavily_service import TavilyService


class RateLimiter:
    """Sliding-window limiter, per client key, in memory (swap for Redis if you scale out)."""

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int) -> Optional[int]:
        """Return None when allowed, else the number of seconds to wait."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return max(1, int(window_seconds - (now - hits[0])) + 1)
        hits.append(now)
        if len(self._hits) > 5000:                 # keep memory bounded
            for k in [k for k, v in self._hits.items() if not v][:1000]:
                self._hits.pop(k, None)
        return None


@dataclass
class Container:
    settings: Settings
    db: Database
    users: UserRepository
    research_repo: ResearchRepository
    briefing_repo: BriefingRepository
    presentation_repo: PresentationRepository
    tavily: TavilyService
    bifrost: BifrostService
    research: ResearchService
    presentation_ai: PresentationAIService
    limiter: RateLimiter

    def startup(self) -> None:
        self.db.init(SCHEMA_SQL)
        self.research.recover()

    async def shutdown(self) -> None:
        await self.research.shutdown()
        await self.tavily.aclose()
        await self.bifrost.aclose()


def build_container(settings: Settings, tavily=None, bifrost=None) -> Container:
    db = Database(settings.database_path)
    research_repo, briefing_repo = ResearchRepository(db), BriefingRepository(db)
    presentation_repo = PresentationRepository(db)
    tavily = tavily or TavilyService(settings)
    bifrost = bifrost or BifrostService(settings)
    research = ResearchService(settings, research_repo, briefing_repo, tavily, BriefingService(settings, bifrost))
    presentation_ai = PresentationAIService(settings, bifrost, presentation_repo, briefing_repo, research_repo)
    return Container(settings, db, UserRepository(db), research_repo, briefing_repo, presentation_repo,
                     tavily, bifrost, research, presentation_ai, RateLimiter())


def get_container(request: Request) -> Container:
    """The container lives on app.state, so tests can build an app around fake services."""
    return request.app.state.container


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_general(request: Request, c: Container = Depends(get_container)) -> None:
    wait = c.limiter.check(f"gen:{client_ip(request, c.settings)}", c.settings.rate_limit_per_minute, 60)
    if wait:
        raise RateLimitedError(f"Too many requests. Try again in {wait}s.", details={"retry_after": wait})


async def rate_limit_research(request: Request, c: Container = Depends(get_container)) -> None:
    wait = c.limiter.check(f"res:{client_ip(request, c.settings)}", c.settings.research_rate_limit_per_hour, 3600)
    if wait:
        minutes = max(1, wait // 60)
        raise RateLimitedError(
            f"Research limit reached to protect free-tier credits. Try again in about {minutes} min.",
            details={"retry_after": wait})


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


async def optional_user(request: Request, c: Container = Depends(get_container)) -> Optional[dict]:
    token = _bearer(request)
    if not token:
        return None
    user_id = decode_token(token, c.settings.jwt_secret)
    return c.users.get(user_id) if user_id else None


async def current_user(user: Optional[dict] = Depends(optional_user)) -> dict:
    if user is None:
        raise AuthError("Sign in to continue.")
    return user


async def research_user(user: Optional[dict] = Depends(optional_user),
                        c: Container = Depends(get_container)) -> Optional[dict]:
    if c.settings.require_auth and user is None:
        raise AuthError("Sign in to run research.")
    return user
