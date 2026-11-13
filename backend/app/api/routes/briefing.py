from typing import Optional

from fastapi import APIRouter, Depends, Path, Request, Response

from ...dependencies import Container, get_container, rate_limit_general, rate_limit_research, research_user
from ...exceptions import NotFoundError
from ...schemas.briefing_schema import BriefingGenerateRequest, BriefingStatusResponse
from .research import ID_PATTERN, _visible

router = APIRouter(prefix="/briefing", tags=["briefing"])


@router.post("/generate", response_model=BriefingStatusResponse, status_code=202,
             dependencies=[Depends(rate_limit_general)])
async def generate_briefing(body: BriefingGenerateRequest, request: Request, response: Response,
                            user: Optional[dict] = Depends(research_user),
                            c: Container = Depends(get_container)) -> dict:
    """Generate a briefing from finished research. Idempotent: returns the existing briefing unless force=true
    (forcing re-runs the model and uses tokens, so it shares the research rate limit)."""
    _visible(c.research_repo.get(body.research_id), user)
    if body.force:
        await rate_limit_research(request, c)
    row, created = await c.research.generate_briefing(body.research_id, user["id"] if user else None, body.force)
    if not created:
        response.status_code = 200
    return c.research.briefing_view(row)


@router.get("/{briefing_id}", response_model=BriefingStatusResponse, dependencies=[Depends(rate_limit_general)])
async def get_briefing(briefing_id: str = Path(..., pattern=ID_PATTERN), user: Optional[dict] = Depends(research_user),
                       c: Container = Depends(get_container)) -> dict:
    row = c.briefing_repo.get(briefing_id)
    if row is None:
        raise NotFoundError("Briefing not found.")
    _visible(c.research_repo.get(row["research_id"]), user)
    return c.research.briefing_view(row)
