"""Request/response models for the research endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..utils.validation import normalize_entity_name, sanitize_text, validate_public_url

ResearchState = Literal["queued", "running", "completed", "failed"]


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Company or person to research", examples=["Aurelia Systems"])
    url: Optional[str] = Field(None, description="Optional company website or LinkedIn URL")
    meeting_time: Optional[str] = Field(None, description="Meeting date/time, free text", max_length=80)
    purpose: Optional[str] = Field(None, description="Meeting purpose (partnership, sales, investor, ...)",
                                   max_length=200)
    entity_type: Literal["auto", "company", "person"] = "auto"
    auto_brief: bool = Field(True, description="Generate the briefing automatically once research finishes")

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return normalize_entity_name(v)

    @field_validator("url")
    @classmethod
    def _url(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        return validate_public_url(v).url

    @field_validator("meeting_time", "purpose")
    @classmethod
    def _text(cls, v: Optional[str]) -> Optional[str]:
        cleaned = sanitize_text(v, 200)
        return cleaned or None


class ApiErrorInfo(BaseModel):
    code: str
    message: str


class ResearchStatusResponse(BaseModel):
    research_id: str
    status: ResearchState
    stage: str
    progress: int = Field(ge=0, le=100)
    message: str = ""
    entity: Dict[str, Any] = Field(default_factory=dict)
    research_period: Optional[Dict[str, str]] = None
    created_at: str
    updated_at: str
    briefing_id: Optional[str] = None
    sources_count: int = 0
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[ApiErrorInfo] = None
