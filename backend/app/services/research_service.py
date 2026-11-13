"""Research service: owns the asynchronous job lifecycle (create -> research -> optional briefing)."""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import uuid
from datetime import date
from typing import Any, Dict, Optional, Set

from ..agents.research_agent import run_research
from ..config import Settings
from ..database.models import BriefingRepository, ResearchRepository
from ..exceptions import (ConflictError, NotFoundError, ServiceNotConfigured, VelQoraError)
from ..utils.date_utils import IN_WINDOW, UNDATED, research_window
from ..utils.source_utils import public_source
from ..utils.validation import Entity, build_entity, entity_from_dict
from .briefing_service import BriefingService
from .tavily_service import TavilyService

logger = logging.getLogger("velqora.jobs")


class ResearchService:
    def __init__(self, settings: Settings, research: ResearchRepository, briefings: BriefingRepository,
                 tavily: TavilyService, briefing_service: BriefingService):
        self.settings = settings
        self.research = research
        self.briefings = briefings
        self.tavily = tavily
        self.briefing_service = briefing_service
        self._tasks: Set[asyncio.Task] = set()
        self._sem = asyncio.Semaphore(settings.max_concurrent_jobs)

    # ------------------------------------------------------------------ lifecycle
    def recover(self) -> None:
        n = self.research.fail_interrupted() + self.briefings.fail_interrupted()
        if n:
            logger.warning("Marked %d interrupted job(s) as failed after restart", n)

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # ------------------------------------------------------------------ start research
    async def start(self, request: Dict[str, Any], user_id: Optional[str]) -> dict:
        if not self.tavily.configured:
            raise ServiceNotConfigured(
                "Web research is not configured. Add TAVILY_API_KEY to backend/.env and restart the server.",
                code="tavily_not_configured")
        entity = build_entity(request["name"], request.get("url"), request.get("meeting_time"),
                              request.get("purpose"), request.get("entity_type", "auto"))
        start, end = research_window(days=self.settings.research_window_days)
        window = {"start_date": start.isoformat(), "end_date": end.isoformat()}
        research_id = uuid.uuid4().hex
        self.research.create(research_id, user_id, request, dataclasses.asdict(entity), window)
        self._spawn(self._run(research_id, entity, (start, end), bool(request.get("auto_brief", True)), user_id))
        return self.research.get(research_id)

    async def _run(self, research_id: str, entity: Entity, window: tuple, auto_brief: bool,
                   user_id: Optional[str]) -> None:
        briefing_id: Optional[str] = None
        try:
            async with self._sem:
                async def progress(stage: str, pct: int, message: str) -> None:
                    self.research.update(research_id, status="running", stage=stage, progress=pct, message=message)
                    if briefing_id:
                        self.briefings.update(briefing_id, status="running", stage=stage, progress=pct, message=message)

                await progress("validating", 4, "Validating request…")
                result = await run_research(entity, self.tavily, self.settings, window, progress)
                sources, warnings = result["sources"], result["warnings"]
                self.research.update(research_id, sources=sources, warnings=warnings)

                recent = sum(1 for s in sources if s["date_status"] == IN_WINDOW)
                undated = sum(1 for s in sources if s["date_status"] == UNDATED)
                await progress("date_validation", 56,
                               f"Checking dates: {recent} recent, {undated} undated of {len(sources)} sources…")

                if not auto_brief:
                    self.research.update(research_id, status="completed", stage="completed", progress=100,
                                         message="Research complete")
                    return

                briefing_id = uuid.uuid4().hex
                self.briefings.create(briefing_id, research_id, user_id)
                self.research.update(research_id, briefing_id=briefing_id)
                briefing = await self._execute_briefing(briefing_id, research_id, entity, window, sources,
                                                        warnings, progress)
                self.research.update(research_id, status="completed", stage="completed", progress=100,
                                     message="Brief ready ✓", warnings=briefing["warnings"])
        except asyncio.CancelledError:
            raise
        except VelQoraError as exc:
            self._fail(research_id, briefing_id, exc.code, exc.message)
        except Exception:                      # never leak internals to the client
            logger.exception("Unexpected failure in research %s", research_id)
            self._fail(research_id, briefing_id, "internal_error", "Something went wrong while researching. Please try again.")

    def _fail(self, research_id: str, briefing_id: Optional[str], code: str, message: str) -> None:
        err = {"code": code, "message": message}
        self.research.update(research_id, status="failed", stage="failed", message=message, error=err)
        if briefing_id:
            self.briefings.update(briefing_id, status="failed", stage="failed", message=message, error=err)

    # ------------------------------------------------------------------ briefing
    async def _execute_briefing(self, briefing_id: str, research_id: str, entity: Entity, window: tuple,
                                sources: list, warnings: list, progress) -> dict:
        briefing = await self.briefing_service.build(
            research_id=research_id, briefing_id=briefing_id, entity=entity, window=window, sources=sources,
            warnings=warnings, on_progress=progress)
        self.briefings.update(briefing_id, status="completed", stage="completed", progress=100,
                              message="Brief ready ✓", briefing=briefing)
        self.research.update(research_id, sources=sources)       # sources now carry verification evidence
        return briefing

    async def generate_briefing(self, research_id: str, user_id: Optional[str], force: bool = False) -> tuple:
        """Returns (briefing_row, created_new)."""
        row = self.research.get(research_id)
        if row is None:
            raise NotFoundError("Research not found.")
        existing = self.briefings.latest_for_research(research_id)
        if existing and not force and existing["status"] in ("queued", "running", "completed"):
            return existing, False
        if row["status"] in ("queued", "running") and not row.get("sources"):
            raise ConflictError("Research is still running. Wait for it to finish, then generate the briefing.",
                                code="research_not_ready")
        if row["status"] == "failed" or row.get("sources") is None:
            raise ConflictError("This research did not complete, so a briefing cannot be generated.",
                                code="research_failed")
        entity = entity_from_dict(row["entity"])
        window = (date.fromisoformat(row["window"]["start_date"]), date.fromisoformat(row["window"]["end_date"]))
        briefing_id = uuid.uuid4().hex
        self.briefings.create(briefing_id, research_id, user_id)

        async def run() -> None:
            async def progress(stage: str, pct: int, message: str) -> None:
                self.briefings.update(briefing_id, status="running", stage=stage, progress=pct, message=message)
            try:
                async with self._sem:
                    await self._execute_briefing(briefing_id, research_id, entity, window, row["sources"],
                                                 row.get("warnings") or [], progress)
            except asyncio.CancelledError:
                raise
            except VelQoraError as exc:
                self.briefings.update(briefing_id, status="failed", stage="failed", message=exc.message,
                                      error={"code": exc.code, "message": exc.message})
            except Exception:
                logger.exception("Unexpected failure generating briefing %s", briefing_id)
                self.briefings.update(briefing_id, status="failed", stage="failed",
                                      message="Could not generate the briefing.",
                                      error={"code": "internal_error", "message": "Could not generate the briefing."})
        self._spawn(run())
        return self.briefings.get(briefing_id), True

    # ------------------------------------------------------------------ read models
    def research_view(self, row: dict) -> dict:
        sources = row.get("sources") or []
        return {
            "research_id": row["id"], "status": row["status"], "stage": row["stage"], "progress": row["progress"],
            "message": row["message"], "entity": {k: row["entity"].get(k) for k in ("name", "type", "website", "linkedin_url")},
            "research_period": row.get("window"), "created_at": row["created_at"], "updated_at": row["updated_at"],
            "briefing_id": row.get("briefing_id"), "sources_count": len(sources),
            "sources": [public_source(s) for s in sources], "warnings": row.get("warnings") or [],
            "error": row.get("error"),
        }

    @staticmethod
    def briefing_view(row: dict) -> dict:
        return {"briefing_id": row["id"], "research_id": row["research_id"], "status": row["status"],
                "stage": row["stage"], "progress": row["progress"], "message": row["message"],
                "created_at": row["created_at"], "updated_at": row["updated_at"],
                "briefing": row.get("briefing"), "error": row.get("error")}
