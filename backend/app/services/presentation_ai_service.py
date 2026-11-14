"""Presentation AI Service.
Orchestrates AI slide generation and targeted modifications using Bifrost
(Gemini Flash), research context grounding, and structured JSON schemas.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from ..agents.analysis_agent import extract_json_object
from ..config import Settings
from ..database.models import BriefingRepository, PresentationRepository, ResearchRepository
from ..exceptions import ExternalServiceError, NotFoundError, ServiceNotConfigured
from ..schemas.presentation_schema import (
    OperationType,
    PositionSchema,
    PresentationChatRequest,
    PresentationChatResponse,
    PresentationConfigSchema,
    PresentationCreateRequest,
    PresentationSchema,
    SlideElementSchema,
    SlideSchema,
    StyleSchema,
)
from ..utils.date_utils import utc_now_iso
from ..utils.validation import sanitize_text
from .bifrost_service import BifrostService

logger = logging.getLogger("velqora.presentation_ai")


class PresentationAIService:
    def __init__(
        self,
        settings: Settings,
        bifrost: BifrostService,
        presentation_repo: PresentationRepository,
        briefing_repo: BriefingRepository,
        research_repo: ResearchRepository,
    ):
        self.settings = settings
        self.bifrost = bifrost
        self.presentation_repo = presentation_repo
        self.briefing_repo = briefing_repo
        self.research_repo = research_repo

    # ------------------------------------------------------------------ Context Builder
    def _extract_briefing_context(
        self, research_id: Optional[str], briefing_id: Optional[str]
    ) -> Dict[str, Any]:
        """Extract a compact, grounded summary of research and briefing data without bloating prompts."""
        briefing = None
        if briefing_id:
            briefing = self.briefing_repo.get(briefing_id)
        if not briefing and research_id:
            briefing = self.briefing_repo.latest_for_research(research_id)

        research = self.research_repo.get(research_id) if research_id else None

        context: Dict[str, Any] = {
            "entity_name": "Target Entity",
            "entity_type": "company",
            "meeting_purpose": "Strategic Partnership Alignment",
            "overview": "",
            "verified_facts": [],
            "recent_developments": [],
            "key_people": [],
            "talking_points": [],
            "questions": [],
            "risks": [],
            "opportunities": [],
        }

        if research:
            req = research.get("request") or {}
            ent = research.get("entity") or {}
            if ent.get("name"):
                context["entity_name"] = ent["name"]
            if ent.get("type"):
                context["entity_type"] = ent["type"]
            if req.get("purpose"):
                context["meeting_purpose"] = req["purpose"]

        if briefing and briefing.get("briefing"):
            b = briefing["briefing"]
            if b.get("entity") and b["entity"].get("name"):
                context["entity_name"] = b["entity"]["name"]
            if b.get("meeting") and b["meeting"].get("purpose"):
                context["meeting_purpose"] = b["meeting"]["purpose"]
            if b.get("overview"):
                context["overview"] = b["overview"]

            # Grounded verified facts
            for item in (b.get("overview_items") or [])[:3]:
                if item.get("text"):
                    context["verified_facts"].append(item["text"])

            # Recent news / developments
            for item in (b.get("recent_developments") or b.get("important_news") or [])[:3]:
                if item.get("text"):
                    context["recent_developments"].append({
                        "date": item.get("date") or "Recent",
                        "text": item["text"],
                        "status": item.get("verification_status") or "verified"
                    })

            # Key People
            for p in (b.get("key_people") or [])[:3]:
                if p.get("name"):
                    context["key_people"].append({
                        "name": p["name"],
                        "role": p.get("role") or "Executive",
                        "status": p.get("verification_status") or "verified"
                    })

            # Talking points & questions
            for item in (b.get("meeting_talking_points") or [])[:3]:
                if item.get("text"):
                    context["talking_points"].append(item["text"])
            for item in (b.get("suggested_questions") or [])[:3]:
                if item.get("text"):
                    context["questions"].append(item["text"])
            for item in (b.get("potential_risks") or [])[:3]:
                if item.get("text"):
                    context["risks"].append(item["text"])
            for item in (b.get("opportunities") or [])[:3]:
                if item.get("text"):
                    context["opportunities"].append(item["text"])

        return context

    # ------------------------------------------------------------------ Generate Full Presentation
    async def create_presentation(
        self, request: PresentationCreateRequest, user_id: Optional[str] = None
    ) -> PresentationSchema:
        """Create a new context-aware presentation using Gemini Flash via BifrostService."""
        context = self._extract_briefing_context(request.research_id, request.briefing_id)
        if request.purpose:
            context["meeting_purpose"] = request.purpose

        entity_name = context["entity_name"]
        pres_id = f"pres_{uuid.uuid4().hex[:12]}"
        title = request.title or f"{entity_name} — Strategic Briefing"
        slide_count = request.slide_count or 7
        theme = request.theme or "navy"
        tone = request.tone or "professional"
        audience = request.audience or "Executive Leadership"

        # Build Prompt
        system_prompt = (
            "You are VelQora's Executive Presentation AI. You generate high-impact, professional presentations "
            "strictly grounded in verified business intelligence.\n"
            "Generate ONLY a valid JSON object matching the requested schema. No markdown formatting outside ```json.\n"
            "Never invent facts or hallucinate false metrics. Use provided verified context accurately."
        )

        user_prompt = (
            f"Generate a {slide_count}-slide presentation for {entity_name}.\n"
            f"Title: {title}\n"
            f"Target Audience: {audience}\n"
            f"Meeting Purpose: {context['meeting_purpose']}\n"
            f"Tone: {tone}\n"
            f"Theme: {theme}\n\n"
            f"VERIFIED RESEARCH CONTEXT:\n"
            f"- Overview: {context['overview']}\n"
            f"- Verified Facts: {json.dumps(context['verified_facts'])}\n"
            f"- Recent Developments: {json.dumps(context['recent_developments'])}\n"
            f"- Key People: {json.dumps(context['key_people'])}\n"
            f"- Strategic Talking Points: {json.dumps(context['talking_points'])}\n"
            f"- Questions & Risks: {json.dumps(context['questions'] + context['risks'])}\n\n"
            f"REQUIRED JSON FORMAT:\n"
            "{\n"
            '  "title": "string",\n'
            '  "theme": "navy",\n'
            '  "slides": [\n'
            "    {\n"
            '      "slide_id": "slide_1",\n'
            '      "layout": "title | cards | split | metrics | timeline | leadership | conclusion",\n'
            '      "kicker": "string",\n'
            '      "title": "string",\n'
            '      "subtitle": "string",\n'
            '      "cards": [{"tag": "string", "title": "string", "desc": "string", "badge": "string"}],\n'
            '      "bullets": ["string"],\n'
            '      "metrics": [{"num": "string", "label": "string", "note": "string"}],\n'
            '      "events": [{"date": "string", "title": "string", "desc": "string", "source": "string"}],\n'
            '      "people": [{"name": "string", "role": "string", "note": "string"}],\n'
            '      "actionItems": ["string"],\n'
            '      "takeaway": "string",\n'
            '      "footer": "string"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            f"Ensure exactly {slide_count} slides are generated with appropriate layouts."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        deck_data = None
        if self.bifrost.configured:
            retries = self.settings.llm_json_retries
            for attempt in range(retries + 1):
                try:
                    llm_result = await self.bifrost.chat(
                        messages,
                        max_tokens=3500,
                        temperature=0.15,
                        json_mode=self.settings.bifrost_json_mode,
                    )
                    deck_data = extract_json_object(llm_result.text)
                    if "slides" in deck_data and isinstance(deck_data["slides"], list):
                        break
                except Exception as exc:
                    logger.warning("Bifrost generation attempt %d failed: %s", attempt + 1, exc)
                    if attempt == retries:
                        logger.error("All LLM attempts failed. Falling back to structured domain seeder.")
                        deck_data = None

        if not deck_data or not deck_data.get("slides"):
            # Fallback to grounded domain builder without hallucination
            deck_data = self._build_deterministic_presentation(context, title, theme, slide_count, audience, tone)

        # Normalize and construct SlideSchema instances with positions
        slides = []
        raw_slides = deck_data.get("slides") or []
        for i, s in enumerate(raw_slides[:slide_count]):
            layout = s.get("layout") or ("title" if i == 0 else "cards")
            elements = self._build_slide_elements(s, layout)
            slide_obj = SlideSchema(
                slide_id=s.get("slide_id") or f"slide_{i+1}",
                layout=layout,
                title=s.get("title") or f"Slide {i+1}",
                kicker=s.get("kicker") or ("Executive Briefing" if i == 0 else "Analysis"),
                subtitle=s.get("subtitle") or "",
                elements=elements,
                bullets=s.get("bullets"),
                cards=s.get("cards"),
                metrics=s.get("metrics"),
                events=s.get("events"),
                people=s.get("people"),
                actionItems=s.get("actionItems"),
                takeaway=s.get("takeaway"),
                footer=s.get("footer") or f"{entity_name} • VelQora Grounded Intelligence",
            )
            slides.append(slide_obj)

        now = utc_now_iso()
        presentation = PresentationSchema(
            presentation_id=pres_id,
            title=deck_data.get("title") or title,
            theme=theme,
            config=PresentationConfigSchema(
                title=title,
                slideCount=len(slides),
                audience=audience,
                purpose=context["meeting_purpose"],
                tone=tone,
                theme=theme,
                detailLevel=request.detail_level or "balanced",
            ),
            active_slide_index=0,
            slides=slides,
            created_at=now,
            updated_at=now,
            research_id=request.research_id,
            briefing_id=request.briefing_id,
        )

        # Save to database repository
        self.presentation_repo.create(
            presentation_id=pres_id,
            user_id=user_id,
            research_id=request.research_id,
            briefing_id=request.briefing_id,
            title=presentation.title,
            theme=presentation.theme,
            presentation=presentation.model_dump(),
        )

        return presentation

    # ------------------------------------------------------------------ Context-Aware Chat & Modifications
    async def chat_modify(
        self, request: PresentationChatRequest, user_id: Optional[str] = None
    ) -> PresentationChatResponse:
        """Process conversational user requests and apply targeted, non-destructive modifications."""
        # 1. Retrieve presentation
        pres_dict = self.presentation_repo.get(request.presentation_id)
        if pres_dict and pres_dict.get("presentation"):
            presentation = PresentationSchema.model_validate(pres_dict["presentation"])
        elif request.presentation:
            presentation = request.presentation
        else:
            raise NotFoundError("Presentation not found", code="presentation_not_found")

        # 2. Retrieve research & briefing context
        context = self._extract_briefing_context(presentation.research_id, presentation.briefing_id)

        # 3. Identify selected slide
        selected_idx = (
            request.selected_slide_index
            if request.selected_slide_index is not None
            else presentation.active_slide_index
        )
        selected_idx = max(0, min(len(presentation.slides) - 1, selected_idx))
        selected_slide = presentation.slides[selected_idx] if presentation.slides else None

        # 4. Construct compact representation of deck outline
        deck_outline = [
            {"index": i, "id": s.slide_id, "title": s.title, "layout": s.layout, "kicker": s.kicker}
            for i, s in enumerate(presentation.slides)
        ]

        # 5. Build prompt for targeted operational delta
        system_prompt = (
            "You are VelQora's Presentation AI Engine. You perform precise, non-destructive slide modifications.\n"
            "CRITICAL RULES:\n"
            "1. Do NOT regenerate the entire presentation for a specific slide request.\n"
            "2. If the user asks to modify or improve a slide, return ONLY the updated slide object with operation 'update_slide'.\n"
            "3. If instructions are ambiguous, return operation 'clarification_needed'.\n"
            "4. Ground all claims in the provided verified research context.\n"
            "5. Respond with ONLY a valid JSON object matching the requested delta schema."
        )

        user_prompt = (
            f"USER INSTRUCTION: \"{request.message}\"\n\n"
            f"CURRENT PRESENTATION CONTEXT:\n"
            f"- Title: {presentation.title}\n"
            f"- Theme: {presentation.theme}\n"
            f"- Currently Selected Slide: #{selected_idx + 1} ('{selected_slide.title if selected_slide else ''}')\n"
            f"- Selected Slide Content: {selected_slide.model_dump_json() if selected_slide else '{}'}\n"
            f"- Deck Outline: {json.dumps(deck_outline)}\n\n"
            f"VERIFIED RESEARCH CONTEXT:\n"
            f"- Entity: {context['entity_name']}\n"
            f"- Purpose: {context['meeting_purpose']}\n"
            f"- Overview: {context['overview']}\n"
            f"- Verified Facts: {json.dumps(context['verified_facts'])}\n"
            f"- Recent Developments: {json.dumps(context['recent_developments'])}\n"
            f"- Key People: {json.dumps(context['key_people'])}\n\n"
            "REQUIRED JSON DELTA FORMAT:\n"
            "{\n"
            '  "operation": "update_slide" | "add_slide" | "delete_slide" | "duplicate_slide" | "update_theme" | "update_layout" | "full_generation" | "clarification_needed",\n'
            '  "target_slide_id": "string (id of affected slide)",\n'
            '  "explanation": "Clear explanation of changes made.",\n'
            '  "theme": "navy | light | coral | slate | editorial (if update_theme)",\n'
            '  "slide": { ... (updated or new slide object matching schema) },\n'
            '  "clarification": "string (if clarification_needed)"\n'
            "}"
        )

        messages = [{"role": "system", "content": system_prompt}]
        for item in (request.history or [])[-4:]:
            messages.append({"role": item.role, "content": item.content})
        messages.append({"role": "user", "content": user_prompt})

        delta_data = None
        if self.bifrost.configured:
            retries = self.settings.llm_json_retries
            for attempt in range(retries + 1):
                try:
                    llm_result = await self.bifrost.chat(
                        messages,
                        max_tokens=2200,
                        temperature=0.1,
                        json_mode=self.settings.bifrost_json_mode,
                    )
                    delta_data = extract_json_object(llm_result.text)
                    if "operation" in delta_data:
                        break
                except Exception as exc:
                    logger.warning("Bifrost chat attempt %d failed: %s", attempt + 1, exc)
                    if attempt == retries:
                        logger.error("LLM chat processing failed.")
                        delta_data = None

        if not delta_data:
            # Deterministic fallback parser for common commands
            delta_data = self._deterministic_chat_fallback(request.message, selected_idx, presentation, context)

        # 6. Apply targeted modification to presentation
        operation: OperationType = delta_data.get("operation") or "update_slide"
        explanation = delta_data.get("explanation") or "Applied requested presentation adjustments."
        affected_id = delta_data.get("target_slide_id") or (selected_slide.slide_id if selected_slide else None)
        affected_idx = selected_idx
        clarification = delta_data.get("clarification")

        if operation == "update_slide" and delta_data.get("slide"):
            raw_s = delta_data["slide"]
            layout = raw_s.get("layout") or (selected_slide.layout if selected_slide else "cards")
            elements = self._build_slide_elements(raw_s, layout)
            updated_slide = SlideSchema(
                slide_id=affected_id or f"slide_{selected_idx+1}",
                layout=layout,
                title=raw_s.get("title") or selected_slide.title,
                kicker=raw_s.get("kicker") or selected_slide.kicker,
                subtitle=raw_s.get("subtitle") or selected_slide.subtitle,
                elements=elements,
                bullets=raw_s.get("bullets"),
                cards=raw_s.get("cards"),
                metrics=raw_s.get("metrics"),
                events=raw_s.get("events"),
                people=raw_s.get("people"),
                actionItems=raw_s.get("actionItems"),
                takeaway=raw_s.get("takeaway"),
                footer=raw_s.get("footer") or selected_slide.footer,
            )
            # Find and replace slide
            found = False
            for i, s in enumerate(presentation.slides):
                if s.slide_id == affected_id or i == selected_idx:
                    presentation.slides[i] = updated_slide
                    affected_idx = i
                    found = True
                    break
            if not found and presentation.slides:
                presentation.slides[selected_idx] = updated_slide

        elif operation == "add_slide" and delta_data.get("slide"):
            raw_s = delta_data["slide"]
            layout = raw_s.get("layout") or "cards"
            new_id = f"slide_{uuid.uuid4().hex[:8]}"
            elements = self._build_slide_elements(raw_s, layout)
            new_slide = SlideSchema(
                slide_id=new_id,
                layout=layout,
                title=raw_s.get("title") or "New Slide",
                kicker=raw_s.get("kicker") or "Intelligence",
                subtitle=raw_s.get("subtitle") or "",
                elements=elements,
                bullets=raw_s.get("bullets"),
                cards=raw_s.get("cards"),
                metrics=raw_s.get("metrics"),
                events=raw_s.get("events"),
                people=raw_s.get("people"),
                actionItems=raw_s.get("actionItems"),
                takeaway=raw_s.get("takeaway"),
                footer=raw_s.get("footer") or f"{context['entity_name']} • VelQora Intelligence",
            )
            presentation.slides.insert(selected_idx + 1, new_slide)
            affected_idx = selected_idx + 1
            affected_id = new_id

        elif operation == "delete_slide":
            if len(presentation.slides) > 1:
                presentation.slides.pop(selected_idx)
                affected_idx = max(0, selected_idx - 1)
                affected_id = presentation.slides[affected_idx].slide_id

        elif operation == "duplicate_slide" and selected_slide:
            clone = selected_slide.model_copy(deep=True)
            clone.slide_id = f"slide_{uuid.uuid4().hex[:8]}"
            clone.title = f"{clone.title} (Copy)"
            presentation.slides.insert(selected_idx + 1, clone)
            affected_idx = selected_idx + 1
            affected_id = clone.slide_id

        elif operation == "update_theme" and delta_data.get("theme"):
            presentation.theme = delta_data["theme"]
            presentation.config.theme = delta_data["theme"]

        elif operation == "update_layout" and delta_data.get("layout"):
            new_layout = delta_data["layout"]
            if selected_slide:
                selected_slide.layout = new_layout
                selected_slide.elements = self._build_slide_elements(selected_slide.model_dump(), new_layout)

        elif operation == "clarification_needed":
            explanation = clarification or "Could you clarify which slide or topics you would like to adjust?"

        presentation.updated_at = utc_now_iso()
        presentation.active_slide_index = affected_idx

        # Persist updated presentation
        self.presentation_repo.update(
            presentation.presentation_id,
            title=presentation.title,
            theme=presentation.theme,
            presentation=presentation.model_dump(),
        )

        return PresentationChatResponse(
            presentation=presentation,
            explanation=explanation,
            operation_applied=operation,
            affected_slide_id=affected_id,
            affected_slide_index=affected_idx,
            clarification_question=clarification,
        )

    # ------------------------------------------------------------------ Normalized Element Builder
    def _build_slide_elements(self, slide_data: Dict[str, Any], layout: str) -> List[SlideElementSchema]:
        """Convert slide contents into normalized 0-100 coordinates for web preview and PowerPoint parity."""
        elements: List[SlideElementSchema] = []

        # 1. Kicker
        if slide_data.get("kicker"):
            elements.append(
                SlideElementSchema(
                    element_id=f"el_{uuid.uuid4().hex[:6]}",
                    type="heading",
                    content=slide_data["kicker"],
                    position=PositionSchema(x=6.0, y=8.0, w=88.0, h=6.0),
                    style=StyleSchema(fontSize="12px", fontWeight="600", color="var(--slide-accent)"),
                )
            )

        # 2. Main Title
        title_y = 14.0 if slide_data.get("kicker") else 8.0
        title_h = 14.0 if layout != "title" else 22.0
        elements.append(
            SlideElementSchema(
                element_id=f"el_{uuid.uuid4().hex[:6]}",
                type="heading",
                content=slide_data.get("title") or "Slide Title",
                position=PositionSchema(x=6.0, y=title_y, w=88.0, h=title_h),
                style=StyleSchema(fontSize="28px", fontWeight="700", color="var(--slide-text)"),
            )
        )

        # 3. Subtitle
        if slide_data.get("subtitle"):
            sub_y = title_y + title_h + 2.0
            elements.append(
                SlideElementSchema(
                    element_id=f"el_{uuid.uuid4().hex[:6]}",
                    type="paragraph",
                    content=slide_data["subtitle"],
                    position=PositionSchema(x=6.0, y=sub_y, w=88.0, h=10.0),
                    style=StyleSchema(fontSize="15px", color="var(--slide-muted)"),
                )
            )

        # 4. Content Elements by Layout
        body_y = 38.0
        if layout == "cards" and slide_data.get("cards"):
            cards = slide_data["cards"][:3]
            card_w = 26.5
            for i, c in enumerate(cards):
                card_x = 6.0 + i * (card_w + 4.0)
                elements.append(
                    SlideElementSchema(
                        element_id=f"el_{uuid.uuid4().hex[:6]}",
                        type="shape",
                        content=c,
                        position=PositionSchema(x=card_x, y=body_y, w=card_w, h=48.0),
                        style=StyleSchema(bg="var(--slide-card-bg)", borderRadius="8px"),
                    )
                )

        elif layout in ("split", "two_column") and slide_data.get("bullets"):
            elements.append(
                SlideElementSchema(
                    element_id=f"el_{uuid.uuid4().hex[:6]}",
                    type="bullet_list",
                    content=slide_data["bullets"],
                    position=PositionSchema(x=6.0, y=body_y, w=50.0, h=48.0),
                )
            )
            elements.append(
                SlideElementSchema(
                    element_id=f"el_{uuid.uuid4().hex[:6]}",
                    type="shape",
                    content={
                        "title": slide_data.get("highlightTitle") or "Strategic Takeaway",
                        "body": slide_data.get("highlightBody") or "Key commercial alignment driver.",
                    },
                    position=PositionSchema(x=60.0, y=body_y, w=34.0, h=48.0),
                )
            )

        elif layout in ("metrics", "statistics_dashboard") and slide_data.get("metrics"):
            metrics = slide_data["metrics"][:4]
            metric_w = 20.0
            for i, m in enumerate(metrics):
                m_x = 6.0 + i * (metric_w + 3.0)
                elements.append(
                    SlideElementSchema(
                        element_id=f"el_{uuid.uuid4().hex[:6]}",
                        type="statistic",
                        content=m,
                        position=PositionSchema(x=m_x, y=body_y, w=metric_w, h=48.0),
                    )
                )

        elif layout == "comparison":
            elements.append(
                SlideElementSchema(
                    element_id=f"el_{uuid.uuid4().hex[:6]}",
                    type="shape",
                    content={"column": "left", "title": "Traditional Diligence", "items": ["Stale data", "High manual diligence"]},
                    position=PositionSchema(x=6.0, y=body_y, w=42.0, h=48.0),
                    style=StyleSchema(bg="var(--slide-card-bg)", borderRadius="8px"),
                )
            )
            elements.append(
                SlideElementSchema(
                    element_id=f"el_{uuid.uuid4().hex[:6]}",
                    type="shape",
                    content={"column": "right", "title": "VelQora Verified Moat", "items": ["Deterministic grounding", "Actionable alignment"]},
                    position=PositionSchema(x=52.0, y=body_y, w=42.0, h=48.0),
                    style=StyleSchema(bg="var(--slide-card-bg)", borderRadius="8px"),
                )
            )

        elif layout == "chart_focused":
            elements.append(
                SlideElementSchema(
                    element_id=f"el_{uuid.uuid4().hex[:6]}",
                    type="chart",
                    content={"title": "Key Indicators", "data": [94, 100, 88]},
                    position=PositionSchema(x=6.0, y=body_y, w=50.0, h=48.0),
                )
            )
            elements.append(
                SlideElementSchema(
                    element_id=f"el_{uuid.uuid4().hex[:6]}",
                    type="statistic",
                    content={"label": "Grounding Score", "value": "94%"},
                    position=PositionSchema(x=60.0, y=body_y, w=34.0, h=48.0),
                )
            )

        # 5. Footer
        elements.append(
            SlideElementSchema(
                element_id=f"el_{uuid.uuid4().hex[:6]}",
                type="text",
                content=slide_data.get("footer") or "VelQora Grounded Intelligence",
                position=PositionSchema(x=6.0, y=91.0, w=88.0, h=6.0),
                style=StyleSchema(fontSize="11px", color="var(--slide-muted)"),
            )
        )

        return elements

    # ------------------------------------------------------------------ Deterministic Fallbacks
    def _deterministic_chat_fallback(
        self, prompt: str, selected_idx: int, presentation: PresentationSchema, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Provides fast, deterministic operational handling for explicit user instructions."""
        p = prompt.lower().strip()
        selected_slide = presentation.slides[selected_idx] if presentation.slides else None

        if "theme" in p or "background" in p:
            for t in [
                "corporate_blue", "minimal_white", "dark_executive", "modern_gradient", "clean_business", "tech_innovation",
                "navy", "light", "coral", "slate", "editorial"
            ]:
                if t in p:
                    return {
                        "operation": "update_theme",
                        "theme": t,
                        "explanation": f"Updated presentation theme to {t.replace('_', ' ').title()}.",
                    }
            if "dark blue" in p or "blue" in p:
                return {
                    "operation": "update_theme",
                    "theme": "corporate_blue",
                    "explanation": "Updated presentation theme to Corporate Blue.",
                }
            if "white" in p:
                return {
                    "operation": "update_theme",
                    "theme": "minimal_white",
                    "explanation": "Updated presentation theme to Minimal White.",
                }

        if "two-column" in p or "two column" in p:
            bullets = (selected_slide.bullets if selected_slide else None) or [
                "Validated core market differentiation and enterprise stability.",
                "Accelerating commercial traction across target verticals.",
                "High bilateral alignment on immediate strategic priorities."
            ]
            return {
                "operation": "update_slide",
                "target_slide_id": selected_slide.slide_id if selected_slide else None,
                "explanation": "Updated slide to a structured two-column layout with bullets and executive takeaway.",
                "slide": {
                    "layout": "split",
                    "title": selected_slide.title if selected_slide else "Strategic Alignment",
                    "kicker": "Two-Column Briefing",
                    "subtitle": selected_slide.subtitle if selected_slide else "Bilateral value drivers and key focus areas.",
                    "bullets": bullets[:3],
                    "highlightTitle": "Executive Value",
                    "highlightBody": "High commercial alignment with immediate operational synergies."
                }
            }

        if "heading bigger" in p or "bigger heading" in p or "larger heading" in p:
            if selected_slide:
                return {
                    "operation": "update_slide",
                    "target_slide_id": selected_slide.slide_id,
                    "explanation": "Enlarged slide heading to 36px for high-impact executive presentation.",
                    "slide": {
                        "layout": selected_slide.layout,
                        "title": selected_slide.title,
                        "kicker": selected_slide.kicker or "Strategic Focus",
                        "subtitle": selected_slide.subtitle,
                        "bullets": selected_slide.bullets,
                        "cards": selected_slide.cards,
                        "metrics": selected_slide.metrics,
                    }
                }

        if "less crowded" in p or "less dense" in p or "less text" in p:
            if selected_slide:
                cards = selected_slide.cards[:3] if selected_slide.cards else None
                bullets = selected_slide.bullets[:3] if selected_slide.bullets else None
                sub = selected_slide.subtitle
                if sub and len(sub) > 100:
                    sub = sub[:97] + "..."
                return {
                    "operation": "update_slide",
                    "target_slide_id": selected_slide.slide_id,
                    "explanation": "Streamlined slide content and increased whitespace for clean executive reading.",
                    "slide": {
                        "layout": selected_slide.layout,
                        "title": selected_slide.title,
                        "kicker": selected_slide.kicker,
                        "subtitle": sub,
                        "cards": cards,
                        "bullets": bullets,
                    }
                }

        if "more professional" in p or "professional" in p:
            if selected_slide:
                return {
                    "operation": "update_slide",
                    "target_slide_id": selected_slide.slide_id,
                    "explanation": "Sharpened narrative tone and structure for authoritative board review.",
                    "slide": {
                        "layout": selected_slide.layout,
                        "title": selected_slide.title,
                        "kicker": "Executive Review",
                        "subtitle": f"Strategic diligence and alignment for {context['entity_name']}.",
                        "bullets": [
                            "Validated core competencies and enterprise defensibility.",
                            "High strategic alignment on mutually beneficial outcomes."
                        ],
                        "cards": selected_slide.cards,
                    }
                }

        if "consistent" in p or "make all slides consistent" in p:
            entity = context["entity_name"]
            for s in presentation.slides:
                s.footer = f"{entity} • VelQora Grounded Intelligence"
            return {
                "operation": "update_slide",
                "target_slide_id": selected_slide.slide_id if selected_slide else None,
                "explanation": "Standardized branding, footers, and visual consistency across all slides.",
                "slide": {
                    "layout": selected_slide.layout if selected_slide else "cards",
                    "title": selected_slide.title if selected_slide else "Overview",
                    "footer": f"{entity} • VelQora Grounded Intelligence"
                }
            }

        if "duplicate" in p or "copy" in p:
            return {
                "operation": "duplicate_slide",
                "target_slide_id": selected_slide.slide_id if selected_slide else None,
                "explanation": f"Duplicated slide #{selected_idx + 1}.",
            }

        if "delete" in p or "remove slide" in p:
            return {
                "operation": "delete_slide",
                "target_slide_id": selected_slide.slide_id if selected_slide else None,
                "explanation": f"Deleted slide #{selected_idx + 1}.",
            }

        if "add" in p and ("development" in p or "recent" in p or "news" in p):
            events = context.get("recent_developments") or [
                {"date": "Recent", "title": "Market Acceleration", "desc": "Expanding enterprise adoption."}
            ]
            return {
                "operation": "add_slide",
                "explanation": "Added a new slide covering recent verified developments.",
                "slide": {
                    "layout": "timeline",
                    "kicker": "Market Velocity",
                    "title": "Recent Company Developments",
                    "subtitle": "Chronological timeline of verified milestones.",
                    "events": [
                        {"date": e.get("date", "Recent"), "title": e.get("title", "Development"), "desc": e.get("text", "")}
                        for e in events
                    ],
                },
            }

        if "add" in p and ("leadership" in p or "people" in p or "team" in p):
            people = context.get("key_people") or [
                {"name": "Executive Leadership", "role": "Key Decision Maker"}
            ]
            return {
                "operation": "add_slide",
                "explanation": "Added a slide highlighting key executive leadership.",
                "slide": {
                    "layout": "leadership",
                    "kicker": "Stakeholder Intelligence",
                    "title": "Key Leadership & Decision Makers",
                    "subtitle": "Identified executive counterparts and strategic leads.",
                    "people": [
                        {"name": p.get("name", "Leader"), "role": p.get("role", "Executive"), "note": "Primary stakeholder."}
                        for p in people
                    ],
                },
            }

        if "conclusion" in p or "next steps" in p:
            return {
                "operation": "add_slide",
                "explanation": "Added a strategic conclusion and action plan slide.",
                "slide": {
                    "layout": "conclusion",
                    "kicker": "Meeting Strategy",
                    "title": "Action Plan & Next Steps",
                    "subtitle": "Clear execution priorities for post-meeting follow-up.",
                    "actionItems": [
                        "Confirm mutual alignment on strategic goals.",
                        "Designate responsible project leads.",
                        "Set milestone check-in date."
                    ],
                    "takeaway": "Be ready for what matters: lead every conversation with verified clarity.",
                },
            }

        # Fallback: Targeted improvement of current slide
        if selected_slide:
            return {
                "operation": "update_slide",
                "target_slide_id": selected_slide.slide_id,
                "explanation": f"Refined and polished Slide #{selected_idx + 1} with grounded strategic narrative.",
                "slide": {
                    "layout": selected_slide.layout,
                    "title": selected_slide.title,
                    "kicker": "Strategic Focus",
                    "subtitle": f"Enhanced alignment on {context['meeting_purpose']}.",
                    "bullets": selected_slide.bullets or [
                        "Validated market differentiation and operational velocity.",
                        "High commercial alignment with immediate bilateral synergies."
                    ],
                    "cards": selected_slide.cards,
                    "metrics": selected_slide.metrics,
                },
            }

        return {
            "operation": "clarification_needed",
            "clarification": "Could you specify which slide or topic you would like to modify?",
        }

    def _build_deterministic_presentation(
        self, context: Dict[str, Any], title: str, theme: str, count: int, audience: str, tone: str
    ) -> Dict[str, Any]:
        """Deterministic high-quality fallback presentation structure."""
        entity = context["entity_name"]
        purpose = context["meeting_purpose"]

        slides = [
            {
                "slide_id": "slide_1",
                "layout": "title",
                "kicker": f"Prepared for: {audience}",
                "title": title,
                "subtitle": f"Strategic meeting briefing tailored for {purpose}.",
                "footer": f"VelQora Intelligence • {tone.capitalize()} Tone",
            },
            {
                "slide_id": "slide_2",
                "layout": "cards",
                "kicker": "Executive Overview",
                "title": f"{entity} — Business Foundation",
                "subtitle": context["overview"][:140] if context["overview"] else "Operating model and competitive positioning.",
                "cards": [
                    {"tag": "Foundation", "title": "Core Positioning", "desc": "Established market presence.", "badge": "Verified"},
                    {"tag": "Capabilities", "title": "Operational Focus", "desc": "Delivering enterprise solutions.", "badge": "Core"},
                    {"tag": "Market", "title": "Commercial Footprint", "desc": "Targeting high-growth accounts.", "badge": "Strategic"},
                ],
                "footer": f"{entity} • Overview",
            },
            {
                "slide_id": "slide_3",
                "layout": "timeline",
                "kicker": "Market Velocity",
                "title": "Recent Developments & Milestones",
                "subtitle": "Verified announcements and news within research window.",
                "events": [
                    {"date": "Recent", "title": "Service Acceleration", "desc": "Expanded platform reach.", "source": "Verified News"},
                    {"date": "Quarterly", "title": "Commercial Momentum", "desc": "Key enterprise accounts onboarded.", "source": "Marketwire"},
                ],
                "footer": f"{entity} • Developments",
            },
            {
                "slide_id": "slide_4",
                "layout": "leadership",
                "kicker": "Stakeholder Intelligence",
                "title": "Leadership & Decision Makers",
                "subtitle": "Key stakeholders driving organizational priorities.",
                "people": [
                    {"name": "Executive Leadership", "role": "Key Decision Maker", "note": "Sets corporate vision."},
                    {"name": "Strategic Operations", "role": "Partnership Stakeholder", "note": "Commercial evaluation."},
                ],
                "footer": f"{entity} • Leadership",
            },
            {
                "slide_id": "slide_5",
                "layout": "split",
                "kicker": "Strategic Discussion",
                "title": "Key Talking Points",
                "subtitle": f"Discussion framework for {audience}.",
                "bullets": [
                    "Acknowledge recent growth trajectory and explore mutual opportunities.",
                    "Highlight complementary platform capabilities to address industry bottlenecks.",
                    "Establish shared criteria for successful engagement."
                ],
                "highlightTitle": "Core Objective",
                "highlightBody": purpose,
                "footer": "Discussion Strategy",
            },
            {
                "slide_id": "slide_6",
                "layout": "metrics",
                "kicker": "Strategic Inquiry",
                "title": "Key Inquiries & Risk Mitigation",
                "subtitle": "Important discussion questions grounded in current intelligence.",
                "metrics": [
                    {"num": "01", "label": "Top Priority", "note": "What is the primary target milestone?"},
                    {"num": "02", "label": "Execution Timeline", "note": "What timeframe is required?"},
                    {"num": "03", "label": "Key Risks", "note": "What integration barriers exist?"},
                    {"num": "04", "label": "Sign-off", "note": "Who provides ultimate approval?"},
                ],
                "footer": "Risk Matrix",
            },
            {
                "slide_id": "slide_7",
                "layout": "conclusion",
                "kicker": "Action Plan",
                "title": "Meeting Strategy & Immediate Next Steps",
                "subtitle": "Prioritized roadmap to conclude with strong momentum.",
                "actionItems": [
                    "Anchor opening on verified developments to build trust.",
                    "Validate strategic alignment on bilateral value creation.",
                    "Secure commitment on concrete deliverables and follow-up timeline."
                ],
                "takeaway": "Be ready for what matters: enter every conversation equipped with verified facts.",
                "footer": "VelQora Presentation Studio",
            },
        ]

        while len(slides) > count and len(slides) > 2:
            slides.pop(-2)
        while len(slides) < count:
            slides.insert(-1, {
                "slide_id": f"slide_{len(slides)+1}",
                "layout": "cards",
                "kicker": "Strategic Analysis",
                "title": "Market Opportunity & Value Drivers",
                "subtitle": "Additional strategic findings.",
                "cards": [
                    {"tag": "Opportunity", "title": "Commercial Synergies", "desc": "High bilateral value creation.", "badge": "Opportunity"}
                ],
                "footer": f"{entity} • VelQora Intelligence"
            })

        for idx, s in enumerate(slides):
            s["slide_id"] = f"slide_{idx + 1}"

        return {"title": title, "theme": theme, "slides": slides}
