import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from tests.test_health import make_client, wait_for

def test_intelligence_page_structure():
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/pages/intelligence.html")
        assert res.status_code == 200
        html = res.text
        assert "Research Intelligence" in html
        assert "Source Verification" in html
        assert 'id="tabIntel"' in html
        assert 'id="tabVerify"' in html
        assert 'id="panelIntel"' in html
        assert 'id="panelVerify"' in html
        assert 'href="meeting.html"' in html
        assert "Meeting Prep" in html

def test_meeting_page_structure():
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/pages/meeting.html")
        assert res.status_code == 200
        html = res.text
        assert "Meeting Preparation" in html
        assert 'id="meetRoot"' in html
        assert "Back to Intelligence" in html
        assert "Create My Meeting Presentation" in html
        assert 'href="studio.html"' in html

def test_intelligence_and_meeting_backend_data_contracts():
    with make_client() as c:
        # 1. Run full research with auto-briefing
        payload = {
            "name": "Aurelia Systems",
            "url": "https://aurelia.example.com",
            "meeting_time": "Fri, 14 Nov · 11:00 AM",
            "purpose": "Strategic partnership discussion",
            "entity_type": "company",
            "auto_brief": True
        }
        r = c.post("/api/research", json=payload)
        assert r.status_code == 202
        research_id = r.json()["research_id"]

        done = wait_for(c, f"/api/research/{research_id}")
        assert done["status"] == "completed"
        briefing_id = done["briefing_id"]
        assert briefing_id is not None

        # 2. Verify briefing payload contract for Intelligence
        b_res = wait_for(c, f"/api/briefing/{briefing_id}")
        assert b_res["status"] == "completed"
        b = b_res["briefing"]

        # Check all Intelligence fields
        assert "overview" in b and len(b["overview"]) > 0
        assert "overview_items" in b
        assert "key_people" in b and len(b["key_people"]) > 0
        assert "recent_developments" in b and len(b["recent_developments"]) > 0
        assert "important_news" in b
        assert "business_insights" in b
        assert "industry_information" in b
        assert "industry_tags" in b
        assert "sources" in b and len(b["sources"]) > 0
        assert "verification_summary" in b

        # Check Source Verification contract
        summary = b["verification_summary"]
        assert summary["total_claims"] > 0
        assert summary["verified_claims"] > 0
        assert "unverified_claims" in summary
        assert "undated_claims" in summary

        for src in b["sources"]:
            assert "title" in src
            assert "url" in src
            assert "verification_status" in src
            assert src["verification_status"] in ("verified", "unverified", "undated")

        # 3. Check Meeting Preparation contract
        assert "meeting_talking_points" in b and len(b["meeting_talking_points"]) > 0
        assert "suggested_questions" in b and len(b["suggested_questions"]) > 0
        assert "potential_risks" in b and len(b["potential_risks"]) > 0
        assert "opportunities" in b
        assert b["entity"]["name"] == "Aurelia Systems"
        assert b["meeting"]["time"] == "Fri, 14 Nov · 11:00 AM"
        assert b["meeting"]["purpose"] == "Strategic partnership discussion"

        # Check that analysis items are labelled analysis, not verified
        for tp in b["meeting_talking_points"]:
            assert tp["kind"] == "analysis"
            assert tp["verification_status"] == "analysis"

        for q in b["suggested_questions"]:
            assert q["kind"] == "analysis"
            assert q["verification_status"] == "analysis"

        for risk in b["potential_risks"]:
            assert risk["kind"] == "analysis"
            assert risk["verification_status"] == "analysis"
