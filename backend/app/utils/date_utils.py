"""Date helpers: research window, publication-date parsing and validation."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Tuple

from dateutil import parser as dateparser

IN_WINDOW = "in_window"
OUT_OF_WINDOW = "out_of_window"
UNDATED = "undated"

_URL_DATE = re.compile(r"/((?:19|20)\d{2})[/-](0?[1-9]|1[0-2])[/-](0?[1-9]|[12]\d|3[01])(?:[/\-_.]|$)")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def today_utc() -> date:
    return utc_now().date()


def research_window(today: Optional[date] = None, days: int = 30) -> Tuple[date, date]:
    """Inclusive window [today - days, today], relative to the actual execution date."""
    end = today or today_utc()
    return end - timedelta(days=days), end


def parse_date(value, today: Optional[date] = None) -> Optional[date]:
    """Parse an API-provided publication date. Returns None when unparseable or implausible."""
    if value is None:
        return None
    today = today or today_utc()
    parsed: Optional[date] = None
    if isinstance(value, datetime):
        parsed = value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    elif isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            dt = parsedate_to_datetime(text)            # RFC 2822, e.g. "Mon, 03 Nov 2026 14:00:00 GMT"
            parsed = dt.astimezone(timezone.utc).date() if dt.tzinfo else dt.date()
        except (TypeError, ValueError, IndexError):
            try:
                dt = dateparser.parse(text, default=datetime(today.year, 1, 1))
                if dt is None:
                    return None
                parsed = dt.astimezone(timezone.utc).date() if dt.tzinfo else dt.date()
            except (ValueError, OverflowError, TypeError):
                return None
    else:
        return None
    # implausible: before 2000 or more than a day in the future
    if parsed.year < 2000 or parsed > today + timedelta(days=1):
        return None
    return parsed


def date_from_url(url: str, today: Optional[date] = None) -> Optional[date]:
    """Strict /YYYY/MM/DD/ pattern in the URL path (lower confidence than an API date)."""
    if not url:
        return None
    match = _URL_DATE.search(url)
    if not match:
        return None
    try:
        parsed = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
    today = today or today_utc()
    if parsed > today + timedelta(days=1):
        return None
    return parsed


def classify_date(published: Optional[date], start: date, end: date) -> str:
    if published is None:
        return UNDATED
    if start <= published <= end + timedelta(days=1):
        return IN_WINDOW
    return OUT_OF_WINDOW


def relative_label(published: Optional[date], today: Optional[date] = None) -> str:
    if published is None:
        return "undated"
    today = today or today_utc()
    days = (today - published).days
    if days <= 0:
        return "today"
    if days == 1:
        return "1d ago"
    if days < 14:
        return f"{days}d ago"
    if days < 60:
        return f"{days // 7}w ago"
    return published.isoformat()


def parse_meeting_time(raw: Optional[str], today: Optional[date] = None) -> Optional[str]:
    """Best-effort parse of free text like 'Fri, 14 Nov · 11:00'. Returns ISO string or None."""
    if not raw:
        return None
    today = today or today_utc()
    cleaned = raw.replace("·", " ").replace("@", " ").replace(" at ", " ")
    try:
        dt = dateparser.parse(cleaned, fuzzy=True, default=datetime(today.year, today.month, today.day, 9, 0))
    except (ValueError, OverflowError, TypeError):
        return None
    if dt is None:
        return None
    return dt.replace(microsecond=0).isoformat()
