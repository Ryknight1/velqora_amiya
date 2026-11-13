"""Research agent: plans targeted Tavily searches, normalises, de-duplicates and ranks the results."""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from ..config import Settings
from ..exceptions import ExternalServiceError, VelQoraError
from ..services.tavily_service import TavilyService
from ..utils.date_utils import utc_now_iso
from ..utils.source_utils import (assign_ids, dedupe_sources, normalize_result, rank_sources, select_sources)
from ..utils.validation import Entity, purpose_category

logger = logging.getLogger("velqora.research")

ProgressFn = Callable[[str, int, str], Awaitable[None]]


def build_search_plan(entity: Entity, window: Tuple[date, date], settings: Settings) -> List[dict]:
    """A handful of targeted searches (one credit each at basic depth) instead of one broad query."""
    name = entity.name
    quoted = f'"{name}"'
    start, end = window[0].isoformat(), window[1].isoformat()
    _, purpose_terms = purpose_category(entity.purpose)
    person = entity.type == "person"
    plan: List[dict] = [
        {"key": "news", "query": f"{quoted} latest news", "topic": "news", "dated": True, "max": 8},
        {"key": "profile", "topic": "general", "dated": False, "max": 5,
         "query": f"{quoted} professional background biography" if person else f"{quoted} company overview what it does"},
        {"key": "leadership", "topic": "general", "dated": False, "max": 5,
         "query": f"{quoted} current role position company" if person else
         f"{quoted} CEO founder leadership team executives"},
        {"key": "developments", "topic": "general", "dated": True, "max": 6,
         "query": f"{quoted} announcement launch partnership funding {purpose_terms}".strip()},
    ]
    if entity.domain:
        plan.append({"key": "official", "topic": "general", "dated": False, "max": 5,
                     "query": f"{name} newsroom press releases leadership about", "include_domains": [entity.domain]})
    plan.append({"key": "industry", "query": f"{quoted} industry market trends", "topic": "news", "dated": True,
                 "max": 5})
    plan = plan[: settings.tavily_max_searches_per_research]
    for item in plan:
        item["start_date"] = start if item["dated"] else None
        item["end_date"] = end if item["dated"] else None
    return plan


async def run_research(entity: Entity, tavily: TavilyService, settings: Settings, window: Tuple[date, date],
                       on_progress: Optional[ProgressFn] = None) -> Dict:
    plan = build_search_plan(entity, window, settings)
    total = len(plan)
    done = 0
    sem = asyncio.Semaphore(3)
    notify = on_progress or _noop

    async def one(item: dict):
        nonlocal done
        async with sem:
            try:
                data = await tavily.search(
                    item["query"], topic=item["topic"], start_date=item["start_date"], end_date=item["end_date"],
                    max_results=item["max"], include_domains=item.get("include_domains"))
                outcome: Tuple[dict, Optional[dict], Optional[Exception]] = (item, data, None)
            except VelQoraError as exc:
                logger.warning("Search '%s' failed: %s", item["key"], exc.message)
                outcome = (item, None, exc)
            done += 1
            await notify("searching", 8 + int(37 * done / total), f"Searching the web… ({done}/{total})")
            return outcome

    await notify("searching", 8, "Searching the web…")
    outcomes = await asyncio.gather(*(one(i) for i in plan))

    failures = [(i, e) for i, _, e in outcomes if e is not None]
    if len(failures) == total:
        raise failures[0][1]            # nothing worked: surface the real reason (auth, quota, network, ...)
    warnings: List[str] = []
    if failures:
        warnings.append("Some searches failed and were skipped: " + ", ".join(i["key"] for i, _ in failures) + ".")

    await notify("processing", 50, "Reading sources…")
    retrieved_at = utc_now_iso()
    collected: List[dict] = []
    raw_count = 0
    for item, data, _ in outcomes:
        for raw in (data or {}).get("results", []) or []:
            if not isinstance(raw, dict):
                continue
            raw_count += 1
            src = normalize_result(raw, category=item["key"], entity=entity, retrieved_at=retrieved_at,
                                   window_start=window[0], window_end=window[1], min_score=settings.tavily_min_score)
            if src:
                collected.append(src)

    unique = dedupe_sources(collected)
    ranked = rank_sources(unique)
    chosen = rank_sources(select_sources(ranked, settings.max_sources))
    sources = assign_ids(chosen)
    await notify("processing", 52, f"Reading {len(sources)} sources…")
    return {"sources": sources, "searches_run": total - len(failures), "searches_failed": len(failures),
            "results_seen": raw_count, "results_kept": len(unique), "warnings": warnings}


async def _noop(*_args) -> None:
    return None
