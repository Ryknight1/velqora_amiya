"""Structured briefing schema. Every AI-generated field is validated against these models."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .research_schema import ApiErrorInfo

ItemStatus = Literal["verified", "unverified", "undated", "outdated", "analysis", "unavailable"]
SourceStatus = Literal["verified", "unverified", "undated"]


class BriefingItem(BaseModel):
    """One statement. kind: fact (checked against sources) | analysis (AI-generated) | unavailable (gap)."""
    claim_id: Optional[str] = None
    text: str
    kind: Literal["fact", "analysis", "unavailable"]
    verification_status: ItemStatus
    source_ids: List[str] = Field(default_factory=list)
    date: Optional[str] = None
    origin: Optional[str] = None
    note: Optional[str] = None


class KeyPerson(BaseModel):
    name: str
    role: str = ""
    claim_id: Optional[str] = None
    source_ids: List[str] = Field(default_factory=list)
    verification_status: ItemStatus = "verified"


class BriefingEntity(BaseModel):
    name: str
    type: Literal["company", "person", "unknown"] = "unknown"
    website: Optional[str] = None
    linkedin_url: Optional[str] = None


class ResearchPeriod(BaseModel):
    start_date: str
    end_date: str


class MeetingInfo(BaseModel):
    purpose: Optional[str] = None
    time: Optional[str] = None
    time_iso: Optional[str] = None


class BriefingSource(BaseModel):
    source_id: str
    title: str
    url: str
    publisher: str
    published_date: Optional[str] = None
    date_status: Literal["in_window", "out_of_window", "undated"]
    date_source: Optional[str] = None
    retrieved_at: str
    source_type: str
    excerpt: str = ""
    supports_claims: List[str] = Field(default_factory=list)
    verification_status: SourceStatus = "unverified"
    age_label: str = ""


class VerificationSummary(BaseModel):
    verified_claims: int = 0
    unverified_claims: int = 0
    undated_claims: int = 0
    total_claims: int = 0


class AiInfo(BaseModel):
    analysis_available: bool = False
    model: Optional[str] = None


class Briefing(BaseModel):
    model_config = ConfigDict(extra="ignore")

    research_id: str
    briefing_id: str
    status: Literal["completed"] = "completed"
    generated_at: str
    entity: BriefingEntity
    research_period: ResearchPeriod
    meeting: MeetingInfo = Field(default_factory=MeetingInfo)
    overview: str = ""
    overview_items: List[BriefingItem] = Field(default_factory=list)
    key_people: List[KeyPerson] = Field(default_factory=list)
    recent_developments: List[BriefingItem] = Field(default_factory=list)
    important_news: List[BriefingItem] = Field(default_factory=list)
    business_insights: List[BriefingItem] = Field(default_factory=list)
    industry_information: List[BriefingItem] = Field(default_factory=list)
    industry_tags: List[str] = Field(default_factory=list)
    meeting_talking_points: List[BriefingItem] = Field(default_factory=list)
    suggested_questions: List[BriefingItem] = Field(default_factory=list)
    potential_risks: List[BriefingItem] = Field(default_factory=list)
    opportunities: List[BriefingItem] = Field(default_factory=list)
    open_questions: List[BriefingItem] = Field(default_factory=list)
    undated_information: List[BriefingItem] = Field(default_factory=list)
    unverified_claims: List[BriefingItem] = Field(default_factory=list)
    sources: List[BriefingSource] = Field(default_factory=list)
    verification_summary: VerificationSummary = Field(default_factory=VerificationSummary)
    ai: AiInfo = Field(default_factory=AiInfo)
    warnings: List[str] = Field(default_factory=list)


class BriefingGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_id: str = Field(..., pattern=r"^[a-f0-9]{32}$")
    force: bool = Field(False, description="Regenerate even if a briefing already exists (uses LLM tokens)")


class BriefingStatusResponse(BaseModel):
    briefing_id: str
    research_id: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    progress: int = Field(ge=0, le=100)
    message: str = ""
    created_at: str
    updated_at: str
    briefing: Optional[Briefing] = None
    error: Optional[ApiErrorInfo] = None
