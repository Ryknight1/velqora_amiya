from typing import Optional

from fastapi import APIRouter, Depends, Path

from ...dependencies import Container, get_container, rate_limit_general, rate_limit_research, research_user
from ...exceptions import NotFoundError
from ...schemas.research_schema import ResearchRequest, ResearchStatusResponse

router = APIRouter(prefix="/research", tags=["research"])
ID_PATTERN = r"^[a-f0-9]{32}$"


def _visible(row: Optional[dict], user: Optional[dict]) -> dict:
    """Anonymous jobs are reachable by their unguessable id; owned jobs only by their owner."""
    if row is None or (row.get("user_id") and (user is None or user["id"] != row["user_id"])):
        raise NotFoundError("Research not found.")
    return row


@router.post("", status_code=202, response_model=ResearchStatusResponse,
             dependencies=[Depends(rate_limit_general), Depends(rate_limit_research)])
async def start_research(body: ResearchRequest, user: Optional[dict] = Depends(research_user),
                         c: Container = Depends(get_container)) -> dict:
    """Validate the request and start an asynchronous research job. Poll GET /api/research/{id}."""
    row = await c.research.start(body.model_dump(), user["id"] if user else None)
    return c.research.research_view(row)


@router.get("/{research_id}", response_model=ResearchStatusResponse, dependencies=[Depends(rate_limit_general)])
async def get_research(research_id: str = Path(..., pattern=ID_PATTERN), user: Optional[dict] = Depends(research_user),
                       c: Container = Depends(get_container)) -> dict:
    row = _visible(c.research_repo.get(research_id), user)
    return c.research.research_view(row)
