"""Briefing agent: assembles the final structured briefing from verified claims and sources.

Section rules
  * Factual sections contain ONLY verified claims (each with source ids).
  * Claims that are grounded but not confirmed as recent go to `undated_information`.
  * Ungrounded claims go to `unverified_claims` and are excluded from every verified section.
  * Talking points / questions / risks / opportunities are labelled AI analysis (never counted as verified).
  * Gaps are reported as `open_questions` with status "unavailable" instead of being filled in.
"""
from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Dict, List, Optional, Tuple

from ..utils.date_utils import IN_WINDOW, utc_now_iso
from ..utils.source_utils import public_source
from ..utils.validation import Entity, sanitize_text
from .verification_agent import OUTDATED, UNDATED_STATUS, UNVERIFIED, VERIFIED

MAX_NEWS = 6


def new_id() -> str:
    return uuid.uuid4().hex


def _fact_item(r: dict) -> dict:
    return {"claim_id": r["claim_id"], "text": r["text"], "kind": "fact", "verification_status": VERIFIED,
            "source_ids": r["supporting_source_ids"], "date": r.get("date"), "origin": "ai_extracted"}


def _analysis_item(item: dict, kind_label: str = "analysis") -> dict:
    return {"claim_id": None, "text": item["text"], "kind": "analysis", "verification_status": "analysis",
            "source_ids": item.get("source_ids", []), "date": None, "origin": "ai_generated"}


def _headline_excerpt(src: dict) -> str:
    content = sanitize_text(src.get("content"), 400)
    first = re.split(r"(?<=[.!?])\s+", content)[0] if content else ""
    return first[:220]


def build_important_news(sources: List[dict]) -> List[dict]:
    """Deterministic, AI-free list: dated in-window items whose headline/date come straight from the source."""
    news = [s for s in sources if s["date_status"] == IN_WINDOW and
            ({"news", "developments", "official"} & set(s["categories"]))]
    news.sort(key=lambda s: (s["published_date"] or "", -s["priority"]), reverse=True)
    return news[:MAX_NEWS]


def build_briefing(*, research_id: str, briefing_id: str, entity: Entity, window: Tuple[date, date],
                   sources: List[dict], analysis: Optional[dict], verified: List[dict], model: Optional[str],
                   warnings: List[str]) -> dict:
    by_status = lambda status: [r for r in verified if r["verification_status"] == status]
    ok = by_status(VERIFIED)
    section = lambda name: [r for r in ok if r["section"] == name]

    next_claim = len(verified) + 1
    extra_claims: List[dict] = []

    # --- overview text (verified statements only) ---
    overview_items = [_fact_item(r) for r in section("overview")]
    overview = " ".join(i["text"] for i in overview_items)

    # --- people ---
    people = [{"name": r["name"], "role": r.get("role", ""), "claim_id": r["claim_id"],
               "source_ids": r["supporting_source_ids"], "verification_status": VERIFIED}
              for r in section("key_people")]

    # --- important news: straight from dated sources ---
    news_items = []
    for s in build_important_news(sources):
        excerpt = _headline_excerpt(s)
        news_items.append({"claim_id": None, "text": s["title"] + (f" — {excerpt}" if excerpt else ""), "kind": "fact",
                           "verification_status": VERIFIED, "source_ids": [s["source_id"]],
                           "date": s["published_date"], "origin": "source_headline"})

    # --- recent developments (AI-extracted, verified, in window) ---
    developments = [_fact_item(r) for r in section("recent_developments")]
    if not developments and news_items:
        # no AI-derived developments survived: fall back to source headlines (counted as verified claims)
        for n in news_items[:3]:
            cid = f"C{next_claim}"
            next_claim += 1
            dev = dict(n, claim_id=cid)
            developments.append(dev)
            extra_claims.append(dev)
            for sid in dev["source_ids"]:
                src = next(s for s in sources if s["source_id"] == sid)
                src["supports_claims"].append(cid)
                src["verification_status"] = "verified"
    insights = [_fact_item(r) for r in section("business_insights")]
    industry = [_fact_item(r) for r in section("industry_information")]

    # --- AI analysis (clearly labelled) ---
    a = analysis or {}
    talking = [_analysis_item(i) for i in a.get("meeting_talking_points", [])]
    questions = [_analysis_item(i) for i in a.get("suggested_questions", [])]
    risks = [_analysis_item(i) for i in a.get("potential_risks", [])]
    opportunities = [_analysis_item(i) for i in a.get("opportunities", [])]
    tags = list(a.get("industry_tags", []))

    # --- excluded / flagged ---
    undated = [{"claim_id": r["claim_id"], "text": r["text"], "kind": "fact", "verification_status": r["verification_status"],
                "source_ids": r["supporting_source_ids"], "date": r.get("date"), "origin": "ai_extracted",
                "note": r.get("reason")} for r in verified if r["verification_status"] in (UNDATED_STATUS, OUTDATED)]
    unverified = [{"claim_id": r["claim_id"], "text": r["text"], "kind": "fact", "verification_status": UNVERIFIED,
                   "source_ids": [], "date": None, "origin": "ai_extracted", "note": r.get("reason")}
                  for r in by_status(UNVERIFIED)]

    # --- open questions: model-provided + honest gap notes ---
    opens = [{"claim_id": None, "text": i["text"], "kind": "analysis", "verification_status": "analysis",
              "source_ids": [], "date": None, "origin": "ai_generated"} for i in a.get("open_questions", [])]

    def gap(text: str) -> None:
        opens.append({"claim_id": None, "text": text, "kind": "unavailable", "verification_status": "unavailable",
                      "source_ids": [], "date": None, "origin": "system"})
    if not sources:
        gap("No relevant sources were found for this name. Check the spelling or add the company website.")
    else:
        if not overview:
            gap("No verified company/person overview could be established from the retrieved sources.")
        if not people:
            gap("No key people could be verified from the retrieved sources.")
        if not news_items and not developments:
            gap(f"No dated developments from the last {(window[1] - window[0]).days} days were found.")
        if analysis is None:
            gap("AI analysis was unavailable, so talking points, questions and risks were not generated.")

    # --- verification summary (facts only) ---
    verified_n = len(ok) + len(extra_claims)
    summary = {"verified_claims": verified_n, "unverified_claims": len(unverified),
               "undated_claims": len(undated), "total_claims": len(verified) + len(extra_claims)}

    return {
        "research_id": research_id, "briefing_id": briefing_id, "status": "completed",
        "generated_at": utc_now_iso(),
        "entity": entity.public(),
        "research_period": {"start_date": window[0].isoformat(), "end_date": window[1].isoformat()},
        "meeting": {"purpose": entity.purpose, "time": entity.meeting_time_raw, "time_iso": entity.meeting_time_iso},
        "overview": overview, "overview_items": overview_items, "key_people": people,
        "recent_developments": developments, "important_news": news_items,
        "business_insights": insights, "industry_information": industry, "industry_tags": tags,
        "meeting_talking_points": talking, "suggested_questions": questions, "potential_risks": risks,
        "opportunities": opportunities, "open_questions": opens,
        "undated_information": undated, "unverified_claims": unverified,
        "sources": [public_source(s) for s in sources],
        "verification_summary": summary,
        "ai": {"analysis_available": analysis is not None, "model": model},
        "warnings": list(warnings),
    }
