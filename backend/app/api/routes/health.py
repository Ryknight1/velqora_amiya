import asyncio

from fastapi import APIRouter, Depends, Query

from ... import __version__
from ...dependencies import Container, get_container, rate_limit_general
from ...utils.date_utils import utc_now_iso

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> dict:
    """Is the backend process up?"""
    return {"status": "ok", "service": "velqora-backend", "version": __version__, "time": utc_now_iso()}


@router.get("/services", dependencies=[Depends(rate_limit_general)])
async def health_services(deep: bool = Query(False, description="Also run a tiny model completion (uses a few tokens)"),
                          c: Container = Depends(get_container)) -> dict:
    """Configuration + connectivity of FastAPI, Tavily and Bifrost. Tavily is checked through its free
    /usage endpoint (no search credits). Secrets are never returned."""
    tavily, bifrost = await asyncio.gather(c.tavily.health(), c.bifrost.health(deep=deep))
    problems = [name for name, info in (("tavily", tavily), ("bifrost", bifrost)) if info.get("status") != "ok"]
    return {
        "status": "ok" if not problems else "degraded",
        "services": {"fastapi": {"status": "ok", "version": __version__}, "tavily": tavily, "bifrost": bifrost},
        "attention": problems,
    }
