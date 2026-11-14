"""Presentation API routes.
Provides endpoints for AI presentation creation, context-aware chatbot modifications,
presentation state retrieval/updates, version history, and genuine PowerPoint exports.
"""
from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path as FilePath
from typing import Optional

from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.responses import FileResponse

from ...dependencies import (
    Container,
    get_container,
    rate_limit_general,
    rate_limit_research,
    research_user,
)
from ...exceptions import AuthError, NotFoundError, ValidationFailure, VelQoraError
from ...utils.date_utils import utc_now_iso
from ...schemas.presentation_schema import (
    PresentationChatRequest,
    PresentationChatResponse,
    PresentationCreateRequest,
    PresentationExportRequest,
    PresentationExportResponse,
    PresentationHistoryResponse,
    PresentationSchema,
    PresentationUpdateRequest,
    PresentationVersionItem,
    PresentationVersionsResponse,
)

logger = logging.getLogger("velqora.presentation")
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
    if user and row.get("user_id") and row["user_id"] != user.get("id"):
        raise AuthError("You do not have permission to access this presentation.")
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
    if row and user and row.get("user_id") and row["user_id"] != user.get("id"):
        raise AuthError("You do not have permission to modify this presentation.")

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


@router.get("/{presentation_id}/history", response_model=PresentationHistoryResponse,
            dependencies=[Depends(rate_limit_general)])
async def get_presentation_history(
    presentation_id: str = Path(...),
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
) -> PresentationHistoryResponse:
    """Retrieve version history snapshots and current version metadata."""
    row = c.presentation_repo.get(presentation_id)
    if not row:
        raise NotFoundError("Presentation not found.")
    if user and row.get("user_id") and row["user_id"] != user.get("id"):
        raise AuthError("You do not have permission to access this presentation.")
    versions = c.presentation_repo.get_versions(presentation_id)
    summaries = [
        PresentationVersionItem(
            version=v.get("version", idx + 1),
            timestamp=v.get("timestamp", ""),
            summary=v.get("summary", "Saved version"),
            slide_count=len((v.get("presentation") or {}).get("slides") or []),
            title=(v.get("presentation") or {}).get("title"),
        )
        for idx, v in enumerate(versions)
    ]
    return PresentationHistoryResponse(
        presentation_id=presentation_id,
        current_version=row.get("current_version", 1),
        versions=summaries,
    )


@router.get("/{presentation_id}/versions", response_model=PresentationVersionsResponse,
            dependencies=[Depends(rate_limit_general)])
async def get_presentation_versions(
    presentation_id: str = Path(...),
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
) -> PresentationVersionsResponse:
    """Retrieve version history snapshots for a presentation."""
    row = c.presentation_repo.get(presentation_id)
    if not row:
        raise NotFoundError("Presentation not found.")
    if user and row.get("user_id") and row["user_id"] != user.get("id"):
        raise AuthError("You do not have permission to access this presentation.")
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
    row = c.presentation_repo.get(presentation_id)
    if not row:
        raise NotFoundError("Presentation not found.")
    if user and row.get("user_id") and row["user_id"] != user.get("id"):
        raise AuthError("You do not have permission to access this presentation.")
    restored = c.presentation_repo.restore_version(presentation_id, version_num)
    if not restored:
        raise NotFoundError(f"Version {version_num} not found.")
    return PresentationSchema.model_validate(restored)


@router.post("/{presentation_id}/export", response_model=PresentationExportResponse,
             dependencies=[Depends(rate_limit_general)])
async def export_presentation(
    presentation_id: str = Path(...),
    body: Optional[PresentationExportRequest] = None,
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
) -> PresentationExportResponse:
    """Generate an authentic, editable 16:9 widescreen PowerPoint (.pptx) file."""
    row = c.presentation_repo.get(presentation_id)
    if not row or not row.get("presentation"):
        raise NotFoundError("Presentation not found.")
    if user and row.get("user_id") and row["user_id"] != user.get("id"):
        raise AuthError("You do not have permission to export this presentation.")

    pres_dict = row["presentation"]
    try:
        pres_model = PresentationSchema.model_validate(pres_dict)
    except Exception as e:
        raise ValidationFailure(f"Invalid presentation schema: {e}")

    req_format = (body.format if body and body.format else "pptx").lower()
    if req_format != "pptx":
        raise ValidationFailure(f"Unsupported export format '{req_format}'. Currently 'pptx' is supported.")

    export_id = f"exp_{uuid.uuid4().hex[:10]}"
    clean_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', pres_model.title or "Presentation").strip().replace(' ', '_')
    if not clean_title:
        clean_title = "VelQora_Presentation"
    file_name = f"{clean_title}.pptx"

    c.settings.exports_dir.mkdir(parents=True, exist_ok=True)
    file_path = c.settings.exports_dir / f"{presentation_id}_{export_id}.pptx"

    try:
        c.pptx_service.generate(pres_model.model_dump(), file_path)
    except Exception as e:
        logger.error("PowerPoint generation failed for %s: %s", presentation_id, e, exc_info=True)
        raise VelQoraError(f"Failed to generate PowerPoint deck: {str(e)}")

    file_size = file_path.stat().st_size if file_path.exists() else 0

    c.pres_exports_repo.create(
        presentation_id=presentation_id,
        format=req_format,
        file_path=str(file_path),
        file_name=file_name,
        file_size=file_size,
        user_id=user["id"] if user else None,
        version_num=row.get("current_version", 1),
        export_id=export_id,
    )

    download_url = f"/api/presentation/{presentation_id}/download?export_id={export_id}"

    return PresentationExportResponse(
        export_id=export_id,
        presentation_id=presentation_id,
        format=req_format,
        file_name=file_name,
        file_size_bytes=file_size,
        download_url=download_url,
        created_at=utc_now_iso(),
    )


@router.get("/{presentation_id}/download", dependencies=[Depends(rate_limit_general)])
async def download_presentation(
    presentation_id: str = Path(...),
    export_id: Optional[str] = None,
    user: Optional[dict] = Depends(research_user),
    c: Container = Depends(get_container),
):
    """Download the generated editable PowerPoint presentation with path traversal checks."""
    row = c.presentation_repo.get(presentation_id)
    if not row:
        raise NotFoundError("Presentation not found.")
    if user and row.get("user_id") and row["user_id"] != user.get("id"):
        raise AuthError("You do not have permission to download this presentation.")

    export_row = None
    if export_id:
        export_row = c.pres_exports_repo.get(export_id)
        if not export_row or export_row.get("presentation_id") != presentation_id:
            raise NotFoundError("Requested export file record was not found.")
    else:
        export_row = c.pres_exports_repo.latest_for_presentation(presentation_id, format="pptx")

    # If no export record exists yet, generate on the fly
    if not export_row or not export_row.get("file_path"):
        pres_dict = row.get("presentation")
        if not pres_dict:
            raise NotFoundError("Presentation content is empty.")
        pres_model = PresentationSchema.model_validate(pres_dict)
        clean_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', pres_model.title or "Presentation").strip().replace(' ', '_')
        if not clean_title:
            clean_title = "VelQora_Presentation"
        file_name = f"{clean_title}.pptx"
        c.settings.exports_dir.mkdir(parents=True, exist_ok=True)
        gen_export_id = f"exp_{uuid.uuid4().hex[:10]}"
        file_path = c.settings.exports_dir / f"{presentation_id}_{gen_export_id}.pptx"
        c.pptx_service.generate(pres_model.model_dump(), file_path)
        file_size = file_path.stat().st_size
        c.pres_exports_repo.create(
            presentation_id=presentation_id,
            format="pptx",
            file_path=str(file_path),
            file_name=file_name,
            file_size=file_size,
            user_id=user["id"] if user else None,
            version_num=row.get("current_version", 1),
            export_id=gen_export_id,
        )
        export_row = {
            "file_path": str(file_path),
            "file_name": file_name,
        }

    raw_path = FilePath(export_row["file_path"])
    resolved_path = raw_path.resolve()
    resolved_exports = c.settings.exports_dir.resolve()

    # Path traversal security check
    try:
        resolved_path.relative_to(resolved_exports)
    except ValueError:
        logger.warning("Directory traversal attempt detected: %s outside %s", resolved_path, resolved_exports)
        raise AuthError("Invalid file path.")

    if not resolved_path.exists() or not resolved_path.is_file():
        raise NotFoundError("Presentation file could not be found on the server.")

    download_name = export_row.get("file_name") or "VelQora_Presentation.pptx"
    if not download_name.endswith(".pptx"):
        download_name = f"{download_name}.pptx"

    return FileResponse(
        path=str(resolved_path),
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )

