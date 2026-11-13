"""Source normalisation, classification, de-duplication and ranking."""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, Iterable, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .date_utils import (IN_WINDOW, UNDATED, classify_date, date_from_url, parse_date, relative_label)
from .validation import Entity, is_public_host, neutralize_untrusted, sanitize_text

_TRACKING = re.compile(r"^(utm_.*|gclid|fbclid|mc_cid|mc_eid|igshid|ref|ref_src|cmpid|ocid|source|spm)$", re.I)

KNOWN_PUBLISHERS = {
    "reuters.com": "Reuters", "bloomberg.com": "Bloomberg", "ft.com": "Financial Times", "wsj.com": "Wall Street Journal",
    "nytimes.com": "The New York Times", "bbc.com": "BBC", "bbc.co.uk": "BBC", "cnbc.com": "CNBC",
    "techcrunch.com": "TechCrunch", "theverge.com": "The Verge", "forbes.com": "Forbes", "wired.com": "WIRED",
    "economictimes.indiatimes.com": "The Economic Times", "livemint.com": "Mint", "thehindu.com": "The Hindu",
    "business-standard.com": "Business Standard", "moneycontrol.com": "Moneycontrol", "linkedin.com": "LinkedIn",
    "wikipedia.org": "Wikipedia", "en.wikipedia.org": "Wikipedia", "sec.gov": "SEC", "prnewswire.com": "PR Newswire",
    "businesswire.com": "Business Wire", "globenewswire.com": "GlobeNewswire", "crunchbase.com": "Crunchbase",
    "apnews.com": "Associated Press", "theguardian.com": "The Guardian", "economist.com": "The Economist",
    "zdnet.com": "ZDNET", "venturebeat.com": "VentureBeat", "businessinsider.com": "Business Insider",
}
_WIRES = {"prnewswire.com", "businesswire.com", "globenewswire.com", "accesswire.com", "einpresswire.com"}
_REGULATORY = ("sec.gov", "bseindia.com", "nseindia.com", "companieshouse.gov.uk", "mca.gov.in", "sebi.gov.in",
               "europa.eu", "fca.org.uk", "edgar-online.com")
_NEWS = {d for d in KNOWN_PUBLISHERS if d not in {"linkedin.com", "wikipedia.org", "en.wikipedia.org", "sec.gov",
                                                  "prnewswire.com", "businesswire.com", "globenewswire.com",
                                                  "crunchbase.com"}}
_PROFESSIONAL = ("linkedin.com", "crunchbase.com")
_LOW_QUALITY = ("pinterest.", "quora.com", "facebook.com", "instagram.com", "tiktok.com", "reddit.com", "x.com",
                "twitter.com", "youtube.com", "youtu.be", "medium.com", "scribd.com", "slideshare.net")

# lower number = higher priority (matches the research brief's priority list)
PRIORITY = {"official": 1, "press_release": 2, "regulatory": 3, "news": 4, "professional": 5, "industry": 6,
            "reference": 7, "other": 8}


def normalize_url(url: str) -> Optional[str]:
    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    host = parts.hostname.lower().rstrip(".")
    if not is_public_host(host):
        return None
    if host.startswith("www."):
        host = host[4:]
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if not _TRACKING.match(k)])
    path = parts.path or ""
    if path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit(("https", host, path, query, ""))


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _matches(domain: str, candidates: Iterable[str]) -> bool:
    return any(domain == c or domain.endswith("." + c) for c in candidates)


def publisher_from_domain(domain: str) -> str:
    for known, label in KNOWN_PUBLISHERS.items():
        if domain == known or domain.endswith("." + known):
            return label
    labels = domain.split(".")
    core = labels[-3] if len(labels) >= 3 and labels[-2] in {"co", "com", "org", "gov", "ac"} else (
        labels[-2] if len(labels) >= 2 else labels[0])
    return core.replace("-", " ").title()


def classify_source(domain: str, official_domain: Optional[str]) -> str:
    if official_domain and _matches(domain, [official_domain]):
        return "official"
    if _matches(domain, _WIRES):
        return "press_release"
    if _matches(domain, _REGULATORY):
        return "regulatory"
    if _matches(domain, _NEWS):
        return "news"
    if _matches(domain, _PROFESSIONAL):
        return "professional"
    if _matches(domain, ["wikipedia.org"]):
        return "reference"
    if re.search(r"(news|times|post|daily|journal|tribune|herald|gazette|tech|business|finance|review|insider|weekly)",
                 domain):
        return "industry"
    return "other"


def is_low_quality(domain: str) -> bool:
    return any(domain == d.rstrip(".") or domain.endswith("." + d.rstrip(".")) or
               (d.endswith(".") and d in domain) for d in _LOW_QUALITY)


def is_relevant(entity: Entity, title: str, content: str, domain: str) -> bool:
    """Drop results that do not mention the entity (or live on its official domain)."""
    if entity.domain and _matches(domain, [entity.domain]):
        return True
    tokens = entity.name_tokens
    if not tokens:
        return True
    text = f"{title} {content}".lower()
    words = set(re.findall(r"[^\W_]+", text, re.UNICODE))
    present = sum(1 for t in tokens if t in words)
    needed = max(1, -(-len(tokens) * 3 // 4))      # ceil(0.75 * n)
    return present >= needed


def normalize_result(raw: dict, *, category: str, entity: Entity, retrieved_at: str, window_start: date,
                     window_end: date, min_score: float = 0.0, today: Optional[date] = None) -> Optional[dict]:
    """Turn one Tavily result into an internal source record (or None when unusable)."""
    url = normalize_url(raw.get("url", ""))
    if not url:
        return None
    domain = domain_of(url)
    if is_low_quality(domain):
        return None
    score = raw.get("score")
    score = float(score) if isinstance(score, (int, float)) else 0.0
    if score < min_score:
        return None
    title = sanitize_text(raw.get("title"), 220) or domain
    content, flagged = neutralize_untrusted(raw.get("content"), 1200)
    if not is_relevant(entity, title, content, domain):
        return None
    published = parse_date(raw.get("published_date"), today)
    date_source = "api" if published else None
    if published is None:
        published = date_from_url(url, today)
        date_source = "url" if published else None
    stype = classify_source(domain, entity.domain)
    return {
        "title": title, "url": url, "domain": domain, "publisher": publisher_from_domain(domain),
        "published_date": published.isoformat() if published else None, "date_source": date_source,
        "date_status": classify_date(published, window_start, window_end), "retrieved_at": retrieved_at,
        "content": content, "score": score, "categories": [category], "source_type": stype,
        "priority": PRIORITY[stype], "injection_flagged": flagged,
    }


def dedupe_sources(items: List[dict]) -> List[dict]:
    """One record per normalised URL; categories merged; keep the dated / higher-scoring copy."""
    by_url: Dict[str, dict] = {}
    for item in items:
        key = item["url"]
        existing = by_url.get(key)
        if existing is None:
            by_url[key] = dict(item)
            continue
        cats = list(dict.fromkeys(existing["categories"] + item["categories"]))
        better = item if ((item["published_date"] is not None, item["score"]) >
                          (existing["published_date"] is not None, existing["score"])) else existing
        merged = dict(better)
        merged["categories"] = cats
        if len(existing["content"]) > len(merged["content"]):
            merged["content"] = existing["content"]
        by_url[key] = merged
    # same headline from the same publisher on a different URL is still a duplicate
    seen: Dict[tuple, str] = {}
    result: List[dict] = []
    for item in by_url.values():
        sig = (item["domain"], re.sub(r"\W+", " ", item["title"].lower()).strip())
        if sig in seen:
            continue
        seen[sig] = item["url"]
        result.append(item)
    return result


def rank_sources(items: List[dict]) -> List[dict]:
    def key(s: dict):
        recent = 0 if s["date_status"] == IN_WINDOW else (1 if s["date_status"] == UNDATED else 2)
        pub = s["published_date"] or "0000-00-00"
        # priority first (brief's ordering); then in-window, newest, relevance
        return (s["priority"], recent, _neg_date(pub), -s["score"])
    return sorted(items, key=key)


def _neg_date(iso: str):
    return tuple(-int(p) for p in iso.split("-"))


def select_sources(ranked: List[dict], limit: int) -> List[dict]:
    """Cap the list while guaranteeing in-window dated items are not crowded out."""
    if len(ranked) <= limit:
        return list(ranked)
    recent = [s for s in ranked if s["date_status"] == IN_WINDOW]
    reserve = min(len(recent), max(2, limit // 2))
    chosen = {s["url"] for s in recent[:reserve]}
    for s in ranked:
        if len(chosen) >= limit:
            break
        chosen.add(s["url"])
    return [s for s in ranked if s["url"] in chosen]


def assign_ids(items: List[dict]) -> List[dict]:
    for i, item in enumerate(items, start=1):
        item["source_id"] = f"S{i}"
        item.setdefault("supports_claims", [])
        item.setdefault("verification_status", "unverified")
    return items


def public_source(src: dict, today: Optional[date] = None) -> dict:
    """Source as exposed over the API (no raw content, only a short excerpt)."""
    pub = src.get("published_date")
    return {
        "source_id": src["source_id"], "title": src["title"], "url": src["url"], "publisher": src["publisher"],
        "published_date": pub, "date_status": src["date_status"], "date_source": src.get("date_source"),
        "retrieved_at": src["retrieved_at"], "source_type": src["source_type"],
        "excerpt": sanitize_text(src.get("content"), 300), "supports_claims": list(src.get("supports_claims", [])),
        "verification_status": src.get("verification_status", "unverified"),
        "age_label": relative_label(date.fromisoformat(pub) if pub else None, today),
    }
