import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from tests.test_health import make_client, wait_for

def test_homepage_compact_and_cards():
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/pages/index.html")
        assert res.status_code == 200
        html = res.text
        assert "Be Ready for what" in html
        assert "Matters." in html
        assert "Start Your Research →" in html
        assert 'href="research.html"' in html
        assert 'href="intelligence.html"' in html
        assert 'href="meeting.html"' in html
        assert "New Research" in html
        assert "Research Intelligence" in html
        assert "Source Verification" in html
        assert "Meeting Preparation" in html

def test_research_page_structure_and_form():
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/pages/research.html")
        assert res.status_code == 200
        html = res.text
        assert 'name="name"' in html
        assert 'name="url"' in html
        assert 'name="meeting_time"' in html
        assert 'name="entity_type"' in html
        assert 'name="purpose"' in html
        assert "Start Research" in html
        assert 'id="statusWrap"' in html
        assert 'id="stageList"' in html
        assert 'id="activeBanner"' in html

def test_research_api_validation():
    app = create_app()
    with TestClient(app) as client:
        # Empty name rejected
        bad_req = client.post("/api/research", json={"name": ""})
        assert bad_req.status_code == 422

        # SSRF URL rejected
        bad_url = client.post("/api/research", json={"name": "Acme Corp", "url": "http://127.0.0.1:8000"})
        assert bad_url.status_code == 422

        # Non-existent ID 404
        not_found = client.get("/api/research/0123456789abcdef0123456789abcdef")
        assert not_found.status_code == 404

def test_research_and_briefing_lifecycle_e2e():
    with make_client() as c:
        # 1. Start research with actual schema
        payload = {
            "name": "Aurelia Systems",
            "url": "https://aurelia.example.com",
            "meeting_time": "Fri, 14 Nov · 11:00 AM",
            "purpose": "Strategic partnership discussion",
            "entity_type": "company",
            "auto_brief": True
        }
        res = c.post("/api/research", json=payload)
        assert res.status_code == 202
        data = res.json()
        research_id = data["research_id"]
        assert data["status"] in ("queued", "running")
        assert data["entity"]["name"] == "Aurelia Systems"

        # 2. Poll until research and auto-brief complete
        job = wait_for(c, f"/api/research/{research_id}")
        assert job["status"] == "completed"
        assert job["briefing_id"] is not None
        briefing_id = job["briefing_id"]

        # 3. Retrieve briefing
        b_res = wait_for(c, f"/api/briefing/{briefing_id}")
        assert b_res["status"] == "completed"
        assert b_res["briefing"]["entity"]["name"] == "Aurelia Systems"
        assert b_res["briefing"]["verification_summary"]["total_claims"] > 0

        # 4. Idempotency check: duplicate generate call returns existing briefing without re-running
        gen_res = c.post("/api/briefing/generate", json={"research_id": research_id, "force": False})
        assert gen_res.status_code == 200
        assert gen_res.json()["briefing_id"] == briefing_id
