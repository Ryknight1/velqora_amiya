"""Input validation, URL safety (SSRF guard), text sanitisation and prompt-injection defence."""
from __future__ import annotations

import html
import ipaddress
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urlsplit

from .date_utils import parse_meeting_time

CORPORATE_SUFFIXES = {
    "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation", "co", "company", "plc", "gmbh",
    "ag", "sa", "pvt", "private", "pte", "llp", "lp", "bv", "nv", "oy", "ab", "srl", "spa", "holdings",
}
_BLOCKED_HOST_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".corp", ".intranet",
                          ".localdomain", ".home.arpa")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TAGS = re.compile(r"<[^>]*>")
_WS = re.compile(r"\s+")

# Phrases that try to talk to the model instead of describing the world.
_INJECTION = re.compile(
    r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+|your\s+|previous\s+|prior\s+|above\s+|earlier\s+)*"
    r"(instructions?|prompts?|rules?|directions?)"
    r"|system\s+prompt|developer\s+message|you\s+are\s+now\b|act\s+as\s+(an?\s+)?(ai|assistant|system)"
    r"|new\s+instructions?\s*:|<\|?(im_start|im_end|system|assistant)\|?>|\[/?(inst|system)\]"
    r"|reveal\s+(your|the)\s+(prompt|instructions|api\s*key|secrets?)|(print|output|send)\s+(your\s+)?(api\s*key|secrets?|credentials)",
    re.IGNORECASE,
)


@dataclass
class Entity:
    name: str
    type: str = "unknown"                  # company | person | unknown
    website: Optional[str] = None          # normalised https URL
    domain: Optional[str] = None           # official domain (never used for fetching)
    linkedin_url: Optional[str] = None
    purpose: Optional[str] = None
    purpose_category: str = "general"
    meeting_time_raw: Optional[str] = None
    meeting_time_iso: Optional[str] = None
    name_tokens: List[str] = field(default_factory=list)

    def public(self) -> dict:
        return {"name": self.name, "type": self.type, "website": self.website, "linkedin_url": self.linkedin_url}


# ------------------------------------------------------------------ text helpers
def sanitize_text(value, max_len: int = 500) -> str:
    """Plain text only: no HTML, no control characters, collapsed whitespace, bounded length."""
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = _TAGS.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL.sub("", text)
    text = text.replace("<", " ").replace(">", " ")
    text = _WS.sub(" ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def neutralize_untrusted(value, max_len: int = 1200) -> Tuple[str, bool]:
    """Clean web-retrieved text before it can reach a prompt. Returns (text, flagged)."""
    text = sanitize_text(value, max_len * 2)
    text = text.replace("```", "'''")
    flagged = False
    parts = re.split(r"(?<=[.!?])\s+", text)
    kept = []
    for part in parts:
        if _INJECTION.search(part):
            flagged = True
            kept.append("[instruction-like text removed]")
        else:
            kept.append(part)
    cleaned = " ".join(kept)
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "…"
    return cleaned, flagged


# ------------------------------------------------------------------ entity
def normalize_entity_name(raw) -> str:
    name = sanitize_text(raw, 200)
    if len(name) < 2:
        raise ValueError("Enter a company or person name (at least 2 characters).")
    if len(name) > 120:
        raise ValueError("Name is too long (max 120 characters).")
    if not re.search(r"[^\W\d_]", name, re.UNICODE):
        raise ValueError("Name must contain letters.")
    return name


def name_tokens(name: str) -> List[str]:
    tokens = re.findall(r"[^\W_]+", name.lower(), re.UNICODE)
    core = [t for t in tokens if t not in CORPORATE_SUFFIXES]
    return core or tokens


# ------------------------------------------------------------------ URL safety
def is_public_host(host: str) -> bool:
    """Reject localhost, private/reserved IPs and internal-looking names (SSRF guard)."""
    host = (host or "").strip().strip("[]").lower().rstrip(".")
    if not host or host == "localhost":
        return False
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_global
    except ValueError:
        pass
    if "." not in host:
        return False
    if any(host.endswith(suffix) for suffix in _BLOCKED_HOST_SUFFIXES):
        return False
    labels = host.split(".")
    if not re.fullmatch(r"[a-z]{2,63}|xn--[a-z0-9-]{2,59}", labels[-1]):
        return False
    return all(re.fullmatch(r"[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?", label) for label in labels)


@dataclass
class SafeUrl:
    url: str
    host: str
    domain: str
    kind: str                       # website | linkedin
    linkedin_type: Optional[str] = None   # company | person | school | None


def validate_public_url(raw: str) -> SafeUrl:
    """Validate a user-supplied URL. The backend never fetches it; it is only displayed and used
    to derive a domain for search filtering. Raises ValueError with a safe message."""
    text = sanitize_text(raw, 400)
    if not text:
        raise ValueError("URL is empty.")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", text) and not re.match(r"^[^/]+:\d+", text):
            raise ValueError("Only http and https URLs are allowed.")
        text = "https://" + text
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise ValueError("That does not look like a valid URL.")
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed.")
    if parts.username or parts.password:
        raise ValueError("URLs with embedded credentials are not allowed.")
    host = (parts.hostname or "").lower().rstrip(".")
    if port not in (None, 80, 443):
        raise ValueError("Custom ports are not allowed.")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise ValueError("That does not look like a valid URL.")
    if not is_public_host(host):
        raise ValueError("Enter a public website or LinkedIn address.")
    domain = host[4:] if host.startswith("www.") else host
    path = parts.path or ""
    clean = f"https://{host}{path}".rstrip("/") if path not in ("", "/") else f"https://{host}"
    if domain == "linkedin.com" or domain.endswith(".linkedin.com"):
        match = re.match(r"^/(company|in|school)/([^/]+)", path, re.IGNORECASE)
        if not match:
            raise ValueError("Use a LinkedIn company (/company/…) or profile (/in/…) address.")
        kind = {"company": "company", "in": "person", "school": "school"}[match.group(1).lower()]
        return SafeUrl(f"https://www.linkedin.com/{match.group(1).lower()}/{match.group(2)}", host, "linkedin.com",
                       "linkedin", kind)
    return SafeUrl(clean, host, domain, "website")


PURPOSE_TERMS = (
    ("invest", "investor", "funding", "venture", "vc", "fundrais"), "funding investors revenue",
), (
    ("sale", "sell", "pitch", "customer", "procure", "vendor"), "customers pricing expansion",
), (
    ("partner", "alliance", "collab", "integrat"), "partnership alliance",
), (
    ("hire", "recruit", "interview", "candidate", "job"), "hiring team culture",
), (
    ("business development", "bd ", "biz dev"), "partnership expansion",
)


def purpose_category(purpose: Optional[str]) -> Tuple[str, str]:
    """Return (category, extra search terms)."""
    text = (purpose or "").lower()
    names = ["investor", "sales", "partnership", "hiring", "business_development"]
    for (needles, terms), name in zip(PURPOSE_TERMS, names):
        if any(n in text for n in needles):
            return name, terms
    return "general", ""


def build_entity(name: str, url: Optional[str] = None, meeting_time: Optional[str] = None,
                 purpose: Optional[str] = None, entity_type: str = "auto") -> Entity:
    clean_name = normalize_entity_name(name)
    website = domain = linkedin = None
    inferred = "unknown"
    if url and url.strip():
        safe = validate_public_url(url)
        if safe.kind == "linkedin":
            linkedin = safe.url
            inferred = {"company": "company", "person": "person"}.get(safe.linkedin_type or "", "unknown")
        else:
            website, domain, inferred = safe.url, safe.domain, "company"
    tokens = name_tokens(clean_name)
    if inferred == "unknown" and (set(re.findall(r"[a-z]+", clean_name.lower())) & CORPORATE_SUFFIXES):
        inferred = "company"
    etype = entity_type if entity_type in {"company", "person"} else inferred
    clean_purpose = sanitize_text(purpose, 200) or None
    clean_time = sanitize_text(meeting_time, 80) or None
    category, _ = purpose_category(clean_purpose)
    return Entity(
        name=clean_name, type=etype, website=website, domain=domain, linkedin_url=linkedin,
        purpose=clean_purpose, purpose_category=category, meeting_time_raw=clean_time,
        meeting_time_iso=parse_meeting_time(clean_time) if clean_time else None, name_tokens=tokens,
    )


def entity_from_dict(data: dict) -> Entity:
    return Entity(**{k: v for k, v in data.items() if k in Entity.__dataclass_fields__})
