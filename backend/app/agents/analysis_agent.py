"""Analysis agent: sends the collected research to the LLM (through Bifrost) and normalises its JSON.

The model is only a *drafter*. Nothing it says is trusted until the verification agent has matched it
against the retrieved source text.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config import Settings
from ..exceptions import ExternalServiceError
from ..services.bifrost_service import BifrostService
from ..utils.source_utils import select_sources
from ..utils.validation import Entity, sanitize_text
from . import prompts

logger = logging.getLogger("velqora.analysis")

FACT_SECTIONS = ("overview", "key_people", "recent_developments", "business_insights", "industry_information")
ANALYSIS_SECTIONS = ("meeting_talking_points", "suggested_questions", "potential_risks", "opportunities",
                     "open_questions")
MAX_ITEMS = {"overview": 3, "key_people": 6, "recent_developments": 5, "business_insights": 4,
             "industry_information": 3, "meeting_talking_points": 4, "suggested_questions": 4,
             "potential_risks": 3, "opportunities": 2, "open_questions": 3}


# ------------------------------------------------------------------ JSON extraction
def extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    candidate = cleaned[start:end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        data = json.loads(re.sub(r",\s*([}\]])", r"\1", candidate))     # tolerate trailing commas
    if not isinstance(data, dict):
        raise ValueError("JSON root is not an object")
    return data


# ------------------------------------------------------------------ normalisation
def _ids(value: Any, valid: Set[str]) -> List[str]:
    if isinstance(value, str):
        value = re.findall(r"[Ss]?\d+", value)
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for v in value:
        m = re.fullmatch(r"\[?[Ss]?(\d+)\]?", str(v).strip())
        if m and f"S{int(m.group(1))}" in valid and f"S{int(m.group(1))}" not in out:
            out.append(f"S{int(m.group(1))}")
    return out


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        return [value]
    return list(value) if isinstance(value, (list, tuple)) else []


def _items(value: Any, valid: Set[str], limit: int, max_len: int = 260) -> List[dict]:
    out = []
    for el in _as_list(value):
        if isinstance(el, str):
            text, ids = el, []
        elif isinstance(el, dict):
            text = el.get("text") or el.get("claim") or el.get("statement") or el.get("point") or el.get("question") or ""
            ids = _ids(el.get("source_ids") or el.get("sources") or el.get("basis_source_ids") or [], valid)
        else:
            continue
        text = sanitize_text(text, max_len)
        if len(text) >= 8:
            out.append({"text": text, "source_ids": ids})
        if len(out) >= limit:
            break
    return out


def normalize_analysis(raw: Dict[str, Any], valid_ids: Set[str]) -> Dict[str, Any]:
    """Coerce a (possibly sloppy) model reply into the exact shape the pipeline expects."""
    result: Dict[str, Any] = {}
    for section in ("overview", "recent_developments", "business_insights", "industry_information",
                    "meeting_talking_points", "suggested_questions", "potential_risks", "opportunities",
                    "open_questions"):
        result[section] = _items(raw.get(section), valid_ids, MAX_ITEMS[section])
    people = []
    for el in _as_list(raw.get("key_people")):
        if not isinstance(el, dict):
            continue
        name = sanitize_text(el.get("name"), 80)
        if len(name) < 2:
            continue
        people.append({"name": name, "role": sanitize_text(el.get("role") or el.get("title"), 90),
                       "source_ids": _ids(el.get("source_ids") or el.get("sources") or [], valid_ids)})
        if len(people) >= MAX_ITEMS["key_people"]:
            break
    result["key_people"] = people
    tags = []
    for t in _as_list(raw.get("industry_tags")):
        label = sanitize_text(t, 32)
        if 2 <= len(label) <= 32 and label.lower() not in {x.lower() for x in tags}:
            tags.append(label)
        if len(tags) >= 5:
            break
    result["industry_tags"] = tags
    return result


# ------------------------------------------------------------------ run
async def run_analysis(entity: Entity, sources: List[dict], window: Tuple[date, date], llm: BifrostService,
                       settings: Settings) -> Dict[str, Any]:
    """Returns {"analysis": normalised dict, "model": str, "llm_source_ids": [...]}.
    Raises ExternalServiceError / ServiceNotConfigured when the model cannot be used."""
    chosen = select_sources(sources, settings.llm_max_sources)
    valid = {s["source_id"] for s in chosen}
    messages = prompts.build_analysis_messages(entity, chosen, window[0], window[1], settings.llm_snippet_chars)
    attempts = settings.llm_json_retries + 1
    last_error = "invalid JSON"
    model = settings.bifrost_model
    for attempt in range(attempts):
        result = await llm.chat(messages)
        model = result.model
        try:
            raw = extract_json_object(result.text)
            return {"analysis": normalize_analysis(raw, valid), "model": model,
                    "llm_source_ids": sorted(valid, key=lambda s: int(s[1:]))}
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            logger.warning("LLM reply was not usable JSON (attempt %d/%d): %s", attempt + 1, attempts, last_error)
            messages = messages + [{"role": "assistant", "content": result.text[:1500]},
                                   {"role": "user", "content": prompts.JSON_RETRY_MESSAGE}]
    raise ExternalServiceError("The AI model did not return valid JSON. Try again or choose a different model.",
                               code="llm_invalid_json")
