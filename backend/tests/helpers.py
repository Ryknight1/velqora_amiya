"""Shared test doubles. No network is ever used in tests."""
import dataclasses
import json
from datetime import timedelta
from email.utils import format_datetime
from datetime import datetime, timezone

from app.config import Settings
from app.services.http_client import HttpResponse
from app.utils.date_utils import today_utc


def make_settings(**overrides) -> Settings:
    base = dict(jwt_secret="test-secret", database_path=":memory:", tavily_api_key="tvly-test-key-123456",
                bifrost_base_url="http://bifrost.test", bifrost_model="testprovider/test-model",
                tavily_cache_ttl=0, tavily_max_retries=1, bifrost_max_retries=1, rate_limit_per_minute=1000,
                research_rate_limit_per_hour=1000)
    base.update(overrides)
    return dataclasses.replace(Settings(), **base)


class FakeTransport:
    """handler(method, url, json) -> HttpResponse | Exception"""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    async def request(self, method, url, *, headers=None, json=None, params=None, timeout=20.0):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "json": json})
        out = self.handler(method, url, json)
        if isinstance(out, Exception):
            raise out
        return out

    async def aclose(self):
        pass


def json_response(data, status=200, headers=None) -> HttpResponse:
    return HttpResponse(status, json.dumps(data), headers or {})


async def no_sleep(_delay):
    return None


def rfc_date(days_ago: int) -> str:
    dt = datetime.combine(today_utc() - timedelta(days=days_ago), datetime.min.time(), tzinfo=timezone.utc)
    return format_datetime(dt.replace(hour=12), usegmt=True)


def tav(title, url, content, days_ago=None, score=0.9):
    item = {"title": title, "url": url, "content": content, "score": score}
    if days_ago is not None:
        item["published_date"] = rfc_date(days_ago)
    return item


AURELIA_RESULTS = {
    "news": [
        tav("Aurelia Systems raises $40 million Series B", "https://www.reuters.com/business/aurelia-series-b",
            "Aurelia Systems raised $40 million in Series B funding led by Northwind Capital.", 3),
        tav("Aurelia Systems launches Atlas routing platform", "https://techcrunch.com/aurelia-atlas",
            "Aurelia Systems launched Atlas, an AI routing platform for logistics operators.", 8),
        tav("Aurelia Systems old coverage", "https://www.ft.com/aurelia-2025",
            "Aurelia Systems opened an office in Singapore.", 120),
    ],
    "profile": [
        tav("About Aurelia Systems", "https://aurelia.example.com/about",
            "Aurelia Systems builds AI software that optimises freight routing for logistics companies.", None),
        tav("Unrelated page", "https://example.org/other", "A page about gardening tips and soil.", 2),
    ],
    "leadership": [
        tav("Leadership team | Aurelia Systems", "https://aurelia.example.com/team",
            "Maya Chen is the chief executive officer and co-founder of Aurelia Systems.", None),
    ],
}
