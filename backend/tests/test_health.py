"""API-level tests (FastAPI TestClient). Skipped automatically if fastapi/httpx are not installed.
Run:  cd backend && pytest -q"""
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.dependencies import build_container  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.bifrost_service import BifrostService  # noqa: E402
from app.services.http_client import HttpResponse  # noqa: E402
from app.services.tavily_service import TavilyService  # noqa: E402
from tests.helpers import AURELIA_RESULTS, FakeTransport, json_response, make_settings  # noqa: E402
from tests.test_briefing import GOOD_LLM_JSON, llm_reply  # noqa: E402


def tavily_handler(method, url, body):
    if url.endswith("/usage"):
        return json_response({"key": {"usage": 3, "limit": 1000}})
    q = body["query"]
    key = "news" if "latest news" in q else "profile" if "overview" in q else "leadership" if "CEO" in q else None
    return json_response({"results": AURELIA_RESULTS.get(key, [])})


def bifrost_handler(method, url, body):
    if url.endswith("/health"):
        return json_response({"status": "ok"})
    if url.endswith("/v1/models"):
        return json_response({"data": [{"id": "testprovider/test-model"}]})
    return llm_reply(GOOD_LLM_JSON)


def make_client(**overrides):
    settings = make_settings(frontend_dir=make_settings().frontend_dir, **overrides)
    container = build_container(settings, TavilyService(settings, FakeTransport(tavily_handler)),
                                BifrostService(settings, FakeTransport(bifrost_handler)))
    return TestClient(create_app(settings, container))


def wait_for(client, path, done=("completed", "failed"), timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(path).json()
        if data["status"] in done:
            return data
        time.sleep(0.05)
    raise AssertionError("timed out waiting for " + path)


def test_health():
    with make_client() as c:
        r = c.get("/api/health")
        assert r.status_code == 200 and r.json()["status"] == "ok"


def test_health_services_reports_state_without_leaking_secrets():
    with make_client() as c:
        body = c.get("/api/health/services").json()
        assert body["services"]["fastapi"]["status"] == "ok"
        assert body["services"]["tavily"]["status"] == "ok" and body["services"]["bifrost"]["status"] == "ok"
        assert "tvly-test-key" not in str(body)
    with make_client(tavily_api_key="", bifrost_model="") as c:
        body = c.get("/api/health/services").json()
        assert body["status"] == "degraded" and body["services"]["tavily"]["status"] == "not_configured"


def test_research_validation_errors_are_clean():
    with make_client() as c:
        r = c.post("/api/research", json={"name": ""})
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
        r = c.post("/api/research", json={"name": "Aurelia", "url": "http://169.254.169.254/"})
        assert r.status_code == 422 and "public" in r.json()["error"]["message"].lower()
        assert c.post("/api/research", json={"name": "Aurelia", "bogus": 1}).status_code == 422
        assert c.get("/api/research/not-an-id").status_code == 422
        assert c.get("/api/research/" + "0" * 32).status_code == 404


def test_research_requires_tavily_configuration():
    with make_client(tavily_api_key="") as c:
        r = c.post("/api/research", json={"name": "Aurelia Systems"})
        assert r.status_code == 503 and r.json()["error"]["code"] == "tavily_not_configured"


def test_full_pipeline_over_http():
    with make_client() as c:
        r = c.post("/api/research", json={"name": "Aurelia Systems", "url": "https://aurelia.example.com",
                                          "meeting_time": "Fri, 14 Nov · 11:00", "purpose": "Investor meeting"})
        assert r.status_code == 202
        research_id = r.json()["research_id"]
        done = wait_for(c, f"/api/research/{research_id}")
        assert done["status"] == "completed" and done["briefing_id"] and done["sources_count"] > 0
        assert all("url" in s and "content" not in s for s in done["sources"])

        b = wait_for(c, f"/api/briefing/{done['briefing_id']}")
        brief = b["briefing"]
        assert b["status"] == "completed" and brief["verification_summary"]["verified_claims"] == 3
        assert any("Series B" in d["text"] for d in brief["recent_developments"])
        assert not any("Nimbus" in d["text"] for d in brief["recent_developments"])
        assert "tvly-" not in str(b)

        again = c.post("/api/briefing/generate", json={"research_id": research_id})      # idempotent
        assert again.status_code == 200 and again.json()["briefing_id"] == done["briefing_id"]


def test_generate_briefing_rejects_unknown_research_and_bad_ids():
    with make_client() as c:
        assert c.post("/api/briefing/generate", json={"research_id": "f" * 32}).status_code == 404
        assert c.post("/api/briefing/generate", json={"research_id": "nope"}).status_code == 422


def test_rate_limit_protects_credits():
    with make_client(research_rate_limit_per_hour=1) as c:
        assert c.post("/api/research", json={"name": "Aurelia Systems"}).status_code == 202
        r = c.post("/api/research", json={"name": "Aurelia Systems"})
        assert r.status_code == 429 and "Retry-After" in r.headers


def test_auth_flow_hashes_passwords_and_issues_tokens():
    with make_client() as c:
        reg = c.post("/api/auth/register", json={"email": "Maya@Example.com", "password": "correct horse", "name": "Maya"})
        assert reg.status_code == 201 and reg.json()["user"]["email"] == "maya@example.com"
        assert c.post("/api/auth/register", json={"email": "maya@example.com", "password": "correct horse"}).status_code == 409
        assert c.post("/api/auth/login", json={"email": "maya@example.com", "password": "wrong password"}).status_code == 401
        token = c.post("/api/auth/login", json={"email": "maya@example.com", "password": "correct horse"}).json()["access_token"]
        me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200 and me.json()["name"] == "Maya"
        assert c.get("/api/auth/me").status_code == 401
        assert c.post("/api/auth/register", json={"email": "bad", "password": "correct horse"}).status_code == 422


def test_require_auth_mode_and_job_ownership():
    with make_client(require_auth=True) as c:
        assert c.post("/api/research", json={"name": "Aurelia Systems"}).status_code == 401
        tok = c.post("/api/auth/register", json={"email": "a@example.com", "password": "password-1"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        rid = c.post("/api/research", json={"name": "Aurelia Systems"}, headers=h).json()["research_id"]
        assert c.get(f"/api/research/{rid}", headers=h).status_code == 200
        tok2 = c.post("/api/auth/register", json={"email": "b@example.com", "password": "password-2"}).json()["access_token"]
        assert c.get(f"/api/research/{rid}", headers={"Authorization": f"Bearer {tok2}"}).status_code == 404


def test_cors_and_security_headers():
    with make_client() as c:
        r = c.get("/api/health", headers={"Origin": "http://localhost:5500"})
        assert r.headers["access-control-allow-origin"] == "http://localhost:5500"
        assert r.headers["x-content-type-options"] == "nosniff"
        evil = c.get("/api/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in evil.headers
