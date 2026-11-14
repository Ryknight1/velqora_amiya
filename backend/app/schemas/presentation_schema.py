"""Pydantic schemas for the VelQora Presentation Engine.
Defines the validated single source of truth for presentations, slides,
elements, layouts, and AI chat interactions.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

ElementType = Literal[
    "heading",
    "text",
    "paragraph",
    "bullet_list",
    "image",
    "chart",
    "statistic",
    "shape",
    "icon",
    "divider"
]

LayoutType = Literal[
    "title",
    "title_and_content",
    "two_column",
    "image_and_text",
    "statistics_dashboard",
    "timeline",
    "comparison",
    "quote",
    "chart_focused",
    "conclusion",
    "cards",
    "split",
    "metrics",
    "leadership"
]

OperationType = Literal[
    "full_generation",
    "update_slide",
    "add_slide",
    "delete_slide",
    "duplicate_slide",
    "reorder_slides",
    "update_theme",
    "update_element",
    "add_element",
    "delete_element",
    "update_layout",
    "regenerate_slide",
    "clarification_needed"
]


class PositionSchema(BaseModel):
    """Normalized coordinates (0.0 to 100.0 percent) for alignment across web and PowerPoint."""
    x: float = Field(0.0, ge=0.0, le=100.0, description="Horizontal percentage from left")
    y: float = Field(0.0, ge=0.0, le=100.0, description="Vertical percentage from top")
    w: float = Field(100.0, ge=0.0, le=100.0, description="Width percentage")
    h: float = Field(100.0, ge=0.0, le=100.0, description="Height percentage")


class StyleSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fontSize: Optional[str] = None
    fontWeight: Optional[str] = None
    color: Optional[str] = None
    bg: Optional[str] = None
    align: Optional[str] = None
    borderRadius: Optional[str] = None
    padding: Optional[str] = None


class SlideElementSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    element_id: str = Field(default_factory=lambda: f"el_{uuid.uuid4().hex[:8]}")
    type: ElementType = "text"
    content: Any = ""
    position: PositionSchema = Field(default_factory=PositionSchema)
    style: StyleSchema = Field(default_factory=StyleSchema)


class SlideSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slide_id: str = Field(default_factory=lambda: f"slide_{uuid.uuid4().hex[:8]}")
    title: str = "Meeting Slide"
    layout: LayoutType = "cards"
    kicker: Optional[str] = None
    subtitle: Optional[str] = None
    elements: List[SlideElementSchema] = Field(default_factory=list)
    bullets: Optional[List[str]] = None
    cards: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[List[Dict[str, Any]]] = None
    events: Optional[List[Dict[str, Any]]] = None
    people: Optional[List[Dict[str, Any]]] = None
    actionItems: Optional[List[str]] = None
    takeaway: Optional[str] = None
    highlightTitle: Optional[str] = None
    highlightBody: Optional[str] = None
    speaker_notes: Optional[str] = None
    source_references: List[str] = Field(default_factory=list)
    footer: Optional[str] = None


class PresentationConfigSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    slideCount: int = Field(7, ge=1, le=25)
    audience: Optional[str] = "Executive Leadership"
    purpose: Optional[str] = "Strategic Partnership"
    tone: Optional[str] = "professional"
    theme: Optional[str] = "navy"
    detailLevel: Optional[str] = "balanced"
    topicsInclude: List[str] = Field(default_factory=list)
    topicsExclude: List[str] = Field(default_factory=list)


class PresentationSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    presentation_id: str
    title: str
    theme: str = "navy"
    config: PresentationConfigSchema = Field(default_factory=PresentationConfigSchema)
    active_slide_index: int = 0
    slides: List[SlideSchema] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    research_id: Optional[str] = None
    briefing_id: Optional[str] = None


class PresentationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    research_id: Optional[str] = None
    briefing_id: Optional[str] = None
    title: Optional[str] = None
    prompt: Optional[str] = None
    slide_count: int = Field(7, ge=1, le=25)
    audience: Optional[str] = "Executive Leadership"
    purpose: Optional[str] = "Strategic Partnership"
    tone: Optional[str] = "professional"
    theme: Optional[str] = "navy"
    detail_level: Optional[str] = "balanced"
    topics_include: Optional[List[str]] = None
    topics_exclude: Optional[List[str]] = None


class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class PresentationChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    presentation_id: str
    message: str
    selected_slide_id: Optional[str] = None
    selected_slide_index: Optional[int] = None
    history: List[ChatHistoryItem] = Field(default_factory=list)
    presentation: Optional[PresentationSchema] = None


class PresentationChatResponse(BaseModel):
    presentation: PresentationSchema
    explanation: str
    operation_applied: OperationType
    affected_slide_id: Optional[str] = None
    affected_slide_index: Optional[int] = None
    clarification_question: Optional[str] = None


class PresentationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    presentation: PresentationSchema
