"""Integration and unit tests for VelQora Part 6: Advanced Slide Editor.
Tests manual editing schemas, version history snapshots, autosave endpoints,
6 design themes, AI design modifications, and slide management constraints.
"""
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from starlette.testclient import TestClient

from app.database.connection import Database
from app.database.models import SCHEMA_SQL, BriefingRepository, PresentationRepository, ResearchRepository, UserRepository
from app.dependencies import Container, get_container
from app.exceptions import ExternalServiceError
from app.main import app
from app.schemas.presentation_schema import (
    PositionSchema,
    PresentationChatRequest,
    PresentationCreateRequest,
    PresentationSchema,
    PresentationUpdateRequest,
    SlideElementSchema,
    SlideSchema,
    StyleSchema,
)
from app.services.bifrost_service import BifrostService
from app.services.presentation_ai_service import PresentationAIService


@pytest.fixture
def test_client_and_container(tmp_path):
    settings = app.state.container.settings
    db = Database(str(tmp_path / "test_pres_part6.db"))
    db.init(SCHEMA_SQL)

    user_repo = UserRepository(db)
    research_repo = ResearchRepository(db)
    briefing_repo = BriefingRepository(db)
    presentation_repo = PresentationRepository(db)

    mock_bifrost = MagicMock(spec=BifrostService)
    mock_bifrost.configured = True
    mock_bifrost.settings = settings
    mock_bifrost.aclose = AsyncMock()

    pres_ai = PresentationAIService(
        settings=settings,
        bifrost=mock_bifrost,
        presentation_repo=presentation_repo,
        briefing_repo=briefing_repo,
        research_repo=research_repo,
    )

    container = Container(
        settings=settings,
        db=db,
        users=user_repo,
        research_repo=research_repo,
        briefing_repo=briefing_repo,
        presentation_repo=presentation_repo,
        tavily=app.state.container.tavily,
        bifrost=mock_bifrost,
        research=app.state.container.research,
        presentation_ai=pres_ai,
        limiter=app.state.container.limiter,
    )

    app.dependency_overrides[get_container] = lambda: container
    client = TestClient(app)

    yield client, container, mock_bifrost

    app.dependency_overrides.clear()


def test_version_history_save_and_restore_lifecycle(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    # 1. Create a presentation
    create_res = client.post("/api/presentation/create", json={
        "title": "Board Briefing V1",
        "slide_count": 3,
        "theme": "corporate_blue"
    })
    assert create_res.status_code == 201
    pres_data = create_res.json()
    pres_id = pres_data["presentation_id"]

    # 2. Update with version snapshot 1
    pres_data["title"] = "Board Briefing V2 - Polished"
    update_res1 = client.put(f"/api/presentation/{pres_id}", json={
        "presentation": pres_data,
        "summary": "First revision: Polished titles",
        "save_version": True,
    })
    assert update_res1.status_code == 200

    # 3. Update with version snapshot 2
    pres_data["title"] = "Board Briefing V3 - Executive Final"
    pres_data["slides"][0]["title"] = "Strategic Executive Review"
    update_res2 = client.put(f"/api/presentation/{pres_id}", json={
        "presentation": pres_data,
        "summary": "Second revision: Executive final headline",
        "save_version": True,
    })
    assert update_res2.status_code == 200

    # 4. Fetch versions
    versions_res = client.get(f"/api/presentation/{pres_id}/versions")
    assert versions_res.status_code == 200
    versions = versions_res.json()["versions"]
    assert len(versions) == 2
    assert versions[0]["version"] == 1
    assert versions[0]["summary"] == "First revision: Polished titles"
    assert versions[1]["version"] == 2
    assert versions[1]["summary"] == "Second revision: Executive final headline"

    # 5. Restore Version 1
    restore_res = client.post(f"/api/presentation/{pres_id}/restore/1")
    assert restore_res.status_code == 200
    restored = restore_res.json()
    assert restored["title"] == "Board Briefing V2 - Polished"

    # 6. Verify an auto-save version was created before restore
    versions_res_after = client.get(f"/api/presentation/{pres_id}/versions")
    versions_after = versions_res_after.json()["versions"]
    assert len(versions_after) == 3
    assert "Auto-save before restoring Version 1" in versions_after[2]["summary"]


def test_version_restore_not_found(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    create_res = client.post("/api/presentation/create", json={"title": "Draft", "slide_count": 2})
    assert create_res.status_code == 201
    pres_id = create_res.json()["presentation_id"]

    res = client.post(f"/api/presentation/{pres_id}/restore/999")
    assert res.status_code == 404


def test_ai_design_modifications_fallbacks(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    create_res = client.post("/api/presentation/create", json={"title": "Design Test Deck", "slide_count": 4})
    assert create_res.status_code == 201
    pres_id = create_res.json()["presentation_id"]

    # 1. "Make this slide more professional"
    res1 = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Make this slide more professional",
        "selected_slide_index": 1,
    })
    assert res1.status_code == 200
    assert res1.json()["operation_applied"] == "update_slide"
    assert "authoritative board review" in res1.json()["explanation"].lower() or "professional" in res1.json()["explanation"].lower()

    # 2. "Use a two-column layout"
    res2 = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Use a two-column layout",
        "selected_slide_index": 1,
    })
    assert res2.status_code == 200
    assert res2.json()["presentation"]["slides"][1]["layout"] == "split"

    # 3. "Make the heading bigger"
    res3 = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Make the heading bigger",
        "selected_slide_index": 1,
    })
    assert res3.status_code == 200
    assert res3.json()["operation_applied"] == "update_slide"
    assert "enlarged" in res3.json()["explanation"].lower() or "heading" in res3.json()["explanation"].lower()

    # 4. "Change the background to dark blue"
    res4 = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Change the background to dark blue",
    })
    assert res4.status_code == 200
    assert res4.json()["presentation"]["theme"] == "corporate_blue"

    # 5. "Make all slides consistent"
    res5 = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Make all slides consistent",
    })
    assert res5.status_code == 200
    for s in res5.json()["presentation"]["slides"]:
        assert "VelQora Grounded Intelligence" in s["footer"]

    # 6. "Make the presentation less crowded"
    res6 = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Make the presentation less crowded",
        "selected_slide_index": 1,
    })
    assert res6.status_code == 200
    assert "whitespace" in res6.json()["explanation"].lower() or "streamlined" in res6.json()["explanation"].lower()


def test_six_design_themes_support(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    six_themes = [
        "corporate_blue",
        "minimal_white",
        "dark_executive",
        "modern_gradient",
        "clean_business",
        "tech_innovation",
    ]

    for th in six_themes:
        create_res = client.post("/api/presentation/create", json={
            "title": f"Theme Test {th}",
            "slide_count": 2,
            "theme": th
        })
        assert create_res.status_code == 201
        assert create_res.json()["theme"] == th


def test_slide_management_minimum_constraint(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    # Create 1-slide presentation
    create_res = client.post("/api/presentation/create", json={"title": "Single Slide Deck", "slide_count": 1})
    assert create_res.status_code == 201
    pres_id = create_res.json()["presentation_id"]

    # Try to delete the only slide via chat
    del_res = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Delete this slide",
        "selected_slide_index": 0,
    })
    assert del_res.status_code == 200
    # Slides must not be empty
    assert len(del_res.json()["presentation"]["slides"]) == 1


def test_custom_elements_and_position_schema():
    pos = PositionSchema(x=12.5, y=34.0, w=45.0, h=20.0)
    assert pos.x == 12.5
    assert pos.w == 45.0

    style = StyleSchema(
        fontSize="18px",
        fontWeight="600",
        color="#ffffff",
        bg="rgba(255,88,88,0.2)",
        align="center",
        borderRadius="8px"
    )
    assert style.fontSize == "18px"
    assert style.align == "center"

    el = SlideElementSchema(
        element_id="el_test_123",
        type="heading",
        content="Market Moat Analysis",
        position=pos,
        style=style
    )
    assert el.content == "Market Moat Analysis"

    slide = SlideSchema(
        slide_id="slide_custom_1",
        title="Custom Slide",
        layout="cards",
        elements=[el]
    )
    assert len(slide.elements) == 1
    assert slide.elements[0].position.x == 12.5
