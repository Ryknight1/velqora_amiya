"""Presentation API routes.
Provides endpoints for AI presentation creation, context-aware chatbot modifications,
and presentation state retrieval/updates.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Path, Request, Response

from ...dependencies import (
    Container,
    get_container,
    rate_limit_general,
    rate_limit_research,
    research_user,
)
from ...exceptions import NotFoundError
from ...schemas.presentation_schema import (
    PresentationChatRequest,
    PresentationChatResponse,
    PresentationCreateRequest,
    PresentationSchema,
    PresentationUpdateRequest,
    PresentationVersionsResponse,
)

router = APIRouter(prefix="/presentation", tags=["presentation"])


@router.post("/create", response_model=PresentationSchema, status_code=201,
             dependencies=[Depends(rate_limit_general)])
async def create_presentation(
    body: PresentationCreateRequest,
    request: Request,
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
) -> PresentationSchema:
    """Create a new context-aware presentation grounded in research and briefing intelligence."""
    return await c.presentation_ai.create_presentation(body, user_id=user["id"] if user else None)


@router.post("/chat", response_model=PresentationChatResponse,
             dependencies=[Depends(rate_limit_general)])
async def presentation_chat(
    body: PresentationChatRequest,
    request: Request,
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
) -> PresentationChatResponse:
    """Process targeted conversational slide modifications with Gemini Flash via Bifrost."""
    return await c.presentation_ai.chat_modify(body, user_id=user["id"] if user else None)


@router.get("/{presentation_id}", response_model=PresentationSchema,
            dependencies=[Depends(rate_limit_general)])
async def get_presentation(
    presentation_id: str = Path(...),
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
) -> PresentationSchema:
    """Retrieve an existing presentation by its ID."""
    row = c.presentation_repo.get(presentation_id)
    if not row or not row.get("presentation"):
        raise NotFoundError("Presentation not found.")
    return PresentationSchema.model_validate(row["presentation"])


@router.put("/{presentation_id}", response_model=PresentationSchema,
            dependencies=[Depends(rate_limit_general)])
async def update_presentation(
    body: PresentationUpdateRequest,
    presentation_id: str = Path(...),
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
) -> PresentationSchema:
    """Directly persist updated presentation state with autosave/version tracking."""
    row = c.presentation_repo.get(presentation_id)
    pres_data = body.presentation.model_dump()
    if row:
        c.presentation_repo.update(
            presentation_id,
            title=body.presentation.title,
            theme=body.presentation.theme,
            presentation=pres_data,
        )
    else:
        c.presentation_repo.create(
            presentation_id=presentation_id,
            user_id=user["id"] if user else None,
            research_id=body.presentation.research_id,
            briefing_id=body.presentation.briefing_id,
            title=body.presentation.title,
            theme=body.presentation.theme,
            presentation=pres_data,
        )

    if body.save_version or body.summary:
        summary = body.summary or f"Manual update to {body.presentation.title}"
        c.presentation_repo.add_version(presentation_id, summary, pres_data)

    return body.presentation


@router.get("/{presentation_id}/versions", response_model=PresentationVersionsResponse,
            dependencies=[Depends(rate_limit_general)])
async def get_presentation_versions(
    presentation_id: str = Path(...),
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
) -> PresentationVersionsResponse:
    """Retrieve version history snapshots for a presentation."""
    versions = c.presentation_repo.get_versions(presentation_id)
    summaries = [
        {
            "version": v.get("version", idx + 1),
            "timestamp": v.get("timestamp", ""),
            "summary": v.get("summary", "Saved version"),
            "slide_count": len((v.get("presentation") or {}).get("slides") or []),
            "title": (v.get("presentation") or {}).get("title"),
        }
        for idx, v in enumerate(versions)
    ]
    return PresentationVersionsResponse(
        presentation_id=presentation_id,
        versions=summaries,
    )


@router.post("/{presentation_id}/restore/{version_num}", response_model=PresentationSchema,
             dependencies=[Depends(rate_limit_general)])
async def restore_presentation_version(
    presentation_id: str = Path(...),
    version_num: int = Path(...),
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
) -> PresentationSchema:
    """Restore a previously saved version of a presentation."""
    restored = c.presentation_repo.restore_version(presentation_id, version_num)
    if not restored:
        raise NotFoundError(f"Version {version_num} not found.")
    return PresentationSchema.model_validate(restored)

