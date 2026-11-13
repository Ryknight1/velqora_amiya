"""Verification agent: deterministic cross-check of AI-drafted factual claims against retrieved source text.

No extra LLM calls (free-tier / token-budget friendly). A claim is *verified* only when a cited source
contains (a) every number in the claim, (b) most of its proper nouns, and (c) enough of its content words.
It is a grounding heuristic - it proves the claim's wording is present in the source, not that the source
is true - and the briefing says so.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from ..utils.date_utils import IN_WINDOW, OUT_OF_WINDOW, UNDATED
from .analysis_agent import FACT_SECTIONS

VERIFIED, UNVERIFIED, UNDATED_STATUS, OUTDATED = "verified", "unverified", "undated", "outdated"
RECENCY_SECTIONS = {"recent_developments"}

_STOP = set("""a an the and or but if then than that this these those of in on at to for from by with without into over under
about as is are was were be been being has have had do does did will would can could should may might must it its their
his her our your they them he she we you i not no yes also more most other some such only own same so very just
new said says say one two per via after before during between within up down out off again further once here there
when where why how all any both each few many much which who whom whose what while""".split())
_MONTHS = set("""january february march april may june july august september october november december jan feb mar apr jun
jul aug sep sept oct nov dec monday tuesday wednesday thursday friday saturday sunday""".split())
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def stem(word: str) -> str:
    w = word.lower()
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 4 and w.endswith("es"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 4 and w.endswith("e"):
        w = w[:-1]
    return w


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z]+", text.lower())


def numbers_in(text: str) -> Set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUM.findall(text)}


def content_stems(text: str) -> List[str]:
    return [stem(w) for w in _words(text) if w not in _STOP and w not in _MONTHS and len(w) > 2]


def proper_nouns(text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z'’\-]*", text)
    out = []
    for i, tok in enumerate(tokens):
        if i == 0 or not tok[0].isupper() or tok.isupper():
            continue
        low = tok.lower()
        if low in _STOP or low in _MONTHS:
            continue
        out.append(stem(low.replace("'s", "").replace("’s", "")))
    return out


def ground(claim_text: str, source_text: str, min_overlap: float, extra_nouns: Optional[List[str]] = None) -> Tuple[bool, dict]:
    """Return (ok, detail) for one claim against one source's text."""
    src_stems = set(stem(w) for w in _words(source_text))
    src_numbers = numbers_in(source_text)
    claim_numbers = numbers_in(claim_text)
    missing_numbers = sorted(n for n in claim_numbers if n not in src_numbers)

    nouns = proper_nouns(claim_text) + [stem(n) for n in (extra_nouns or [])]
    nouns = list(dict.fromkeys(nouns))
    found_nouns = [n for n in nouns if n in src_stems]
    noun_ratio = (len(found_nouns) / len(nouns)) if nouns else 1.0

    words = list(dict.fromkeys(content_stems(claim_text)))
    overlap = (sum(1 for w in words if w in src_stems) / len(words)) if words else 0.0

    ok = (not missing_numbers) and noun_ratio >= 0.75 and overlap >= min_overlap and len(words) >= 2
    return ok, {"missing_numbers": missing_numbers, "noun_ratio": round(noun_ratio, 2), "overlap": round(overlap, 2)}


def make_claims(analysis: Dict) -> List[dict]:
    """Flatten the factual sections of the analysis into numbered claims."""
    claims: List[dict] = []
    n = 0
    for section in FACT_SECTIONS:
        for item in analysis.get(section, []):
            n += 1
            claim = {"claim_id": f"C{n}", "section": section, "source_ids": list(item.get("source_ids", []))}
            if section == "key_people":
                claim.update(name=item["name"], role=item.get("role", ""),
                             text=f'{item["name"]}, {item["role"]}' if item.get("role") else item["name"])
            else:
                claim["text"] = item["text"]
            claims.append(claim)
    return claims


def _source_text(src: dict) -> str:
    return f'{src.get("title", "")}. {src.get("content", "")}'


def verify_claim(claim: dict, sources: Dict[str, dict], min_overlap: float) -> dict:
    text = claim["text"]
    extra = None
    if claim["section"] == "key_people":
        extra = re.findall(r"[A-Za-z][A-Za-z'’\-]*", claim.get("name", ""))
    cited = [i for i in claim["source_ids"] if i in sources]
    supporting: List[str] = []
    best = {"overlap": 0.0, "noun_ratio": 0.0, "missing_numbers": []}

    def check(sid: str) -> bool:
        nonlocal best
        if claim["section"] == "key_people":
            ok, detail = _verify_person(claim, sources[sid], min_overlap)
        else:
            ok, detail = ground(text, _source_text(sources[sid]), min_overlap, extra)
        if detail["overlap"] >= best["overlap"]:
            best = detail
        return ok

    for sid in cited:                              # 1) the sources the model cited
        if check(sid):
            supporting.append(sid)
    attributed = False
    if not supporting:                             # 2) models often cite the wrong id: look for real support elsewhere
        for sid in sources:
            if sid not in cited and check(sid):
                supporting.append(sid)
                attributed = True
                break                              # one genuine source is enough
    result = dict(claim)
    result["supporting_source_ids"] = supporting
    if not supporting:
        why = "no retrieved source supports this claim"
        if best["missing_numbers"]:
            why += f" (figures not found: {', '.join(best['missing_numbers'])})"
        result.update(verification_status=UNVERIFIED, reason=why, date=None)
        return result

    dates = [(sources[s]["date_status"], sources[s].get("published_date")) for s in supporting]
    in_window = sorted((d for st, d in dates if st == IN_WINDOW and d), reverse=True)
    result["date"] = in_window[0] if in_window else next((d for _, d in dates if d), None)
    if claim["section"] in RECENCY_SECTIONS and not in_window:
        if any(st == UNDATED for st, _ in dates):
            result.update(verification_status=UNDATED_STATUS,
                          reason="Supported by a source with no reliable publication date, so not confirmed as recent.")
        else:
            result.update(verification_status=OUTDATED,
                          reason="Supported only by sources published before the research period.")
        return result
    result["verification_status"] = VERIFIED
    result["reason"] = "supporting source found by verifier (citation corrected)" if attributed else "matches cited source text"
    return result


def _verify_person(claim: dict, src: dict, min_overlap: float) -> Tuple[bool, dict]:
    text = _source_text(src)
    name_ok, name_detail = ground(claim["name"], text, 0.0, re.findall(r"[A-Za-z][A-Za-z'’\-]*", claim["name"]))
    if not name_ok and name_detail["noun_ratio"] < 1.0:
        return False, name_detail
    role = claim.get("role", "")
    if not role:
        return True, name_detail
    role_stems = list(dict.fromkeys(content_stems(role)))
    src_stems = set(stem(w) for w in _words(text))
    share = (sum(1 for w in role_stems if w in src_stems) / len(role_stems)) if role_stems else 1.0
    detail = {"missing_numbers": [], "noun_ratio": name_detail["noun_ratio"], "overlap": round(share, 2)}
    return share >= 0.99, detail          # every word of the role must appear: one wrong word changes the meaning


def verify_all(claims: List[dict], sources: List[dict], min_overlap: float) -> List[dict]:
    by_id = {s["source_id"]: s for s in sources}
    results = [verify_claim(c, by_id, min_overlap) for c in claims]
    # write the evidence back onto the sources
    for s in sources:
        s["supports_claims"] = []
    for r in results:
        if r["verification_status"] in (VERIFIED, UNDATED_STATUS, OUTDATED):
            for sid in r["supporting_source_ids"]:
                if r["claim_id"] not in by_id[sid]["supports_claims"]:
                    by_id[sid]["supports_claims"].append(r["claim_id"])
    for s in sources:
        has_verified = any(r["claim_id"] in s["supports_claims"] and r["verification_status"] == VERIFIED
                           for r in results)
        s["verification_status"] = ("verified" if has_verified else
                                    ("undated" if s["date_status"] == UNDATED else "unverified"))
    return results
