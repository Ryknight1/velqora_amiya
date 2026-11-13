"""Briefing service: runs analysis -> verification -> briefing assembly for a finished research run."""
from __future__ import annotations

import logging
from datetime import date
from typing import Awaitable, Callable, List, Optional, Tuple

from ..agents import briefing_agent, verification_agent
from ..agents.analysis_agent import run_analysis
from ..config import Settings
from ..exceptions import ExternalServiceError, ServiceNotConfigured
from ..schemas.briefing_schema import Briefing
from ..utils.validation import Entity
from .bifrost_service import BifrostService

logger = logging.getLogger("velqora.briefing")

ProgressFn = Callable[[str, int, str], Awaitable[None]]


class BriefingService:
    def __init__(self, settings: Settings, bifrost: BifrostService):
        self.settings = settings
        self.bifrost = bifrost

    async def build(self, *, research_id: str, briefing_id: str, entity: Entity, window: Tuple[date, date],
                    sources: List[dict], warnings: List[str], on_progress: Optional[ProgressFn] = None) -> dict:
        notify = on_progress or _noop
        warnings = list(warnings)
        analysis: Optional[dict] = None
        model: Optional[str] = None

        if any(s.get("injection_flagged") for s in sources):
            warnings.append("Some web pages contained instruction-like text; it was removed and never followed.")

        if sources:
            await notify("analyzing", 60, "Mapping key people…")
            try:
                out = await run_analysis(entity, sources, window, self.bifrost, self.settings)
                analysis, model = out["analysis"], out["model"]
            except (ExternalServiceError, ServiceNotConfigured) as exc:
                logger.warning("AI analysis unavailable: %s", exc.message)
                warnings.append(f"AI analysis unavailable: {exc.message}")
        else:
            warnings.append("No relevant sources were retrieved, so no analysis was attempted.")

        await notify("verifying", 82, "Verifying claims…")
        claims = verification_agent.make_claims(analysis) if analysis else []
        verified = verification_agent.verify_all(claims, sources, self.settings.verify_min_overlap)

        await notify("preparing", 92, "Preparing your brief…")
        draft = briefing_agent.build_briefing(
            research_id=research_id, briefing_id=briefing_id, entity=entity, window=window, sources=sources,
            analysis=analysis, verified=verified, model=model, warnings=warnings)
        return Briefing.model_validate(draft).model_dump()      # schema-validated, consistent JSON


async def _noop(*_args) -> None:
    return None
