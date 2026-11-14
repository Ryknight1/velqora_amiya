"""Integration and unit tests for VelQora Part 5: AI Presentation Engine."""
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from starlette.testclient import TestClient

from app.database.connection import Database
from app.database.models import SCHEMA_SQL, BriefingRepository, PresentationRepository, ResearchRepository, UserRepository
from app.dependencies import Container, build_container, get_container
from app.exceptions import ExternalServiceError, NotFoundError
from app.main import app
from app.schemas.presentation_schema import (
    PresentationChatRequest,
    PresentationChatResponse,
    PresentationCreateRequest,
    PresentationSchema,
    SlideSchema,
)
from app.services.bifrost_service import BifrostService, LLMResult
from app.services.presentation_ai_service import PresentationAIService


@pytest.fixture
def test_client_and_container(tmp_path):
    settings = app.state.container.settings
    db = Database(str(tmp_path / "test_pres.db"))
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


def test_presentation_create_endpoint_deterministic(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container
    # When bifrost returns empty / fails, deterministic fallback works
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM unavailable"))

    res = client.post("/api/presentation/create", json={
        "title": "Stripe — Strategic Briefing",
        "slide_count": 7,
        "audience": "Executive Leadership",
        "purpose": "Strategic Partnership",
        "tone": "professional",
        "theme": "navy"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Stripe — Strategic Briefing"
    assert data["theme"] == "navy"
    assert len(data["slides"]) == 7
    assert data["slides"][0]["layout"] == "title"

    # Normalized coordinates check on elements
    first_slide = data["slides"][0]
    assert len(first_slide["elements"]) > 0
    kicker_el = first_slide["elements"][0]
    assert 0.0 <= kicker_el["position"]["x"] <= 100.0
    assert 0.0 <= kicker_el["position"]["y"] <= 100.0
    assert 0.0 <= kicker_el["position"]["w"] <= 100.0
    assert 0.0 <= kicker_el["position"]["h"] <= 100.0


def test_presentation_create_with_llm_json(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container

    mock_llm_json = {
        "title": "Acme AI — Investor Deck",
        "theme": "slate",
        "slides": [
            {
                "slide_id": "slide_1",
                "layout": "title",
                "kicker": "Investor Pitch",
                "title": "Acme AI: Autonomous Scalability",
                "subtitle": "Transforming enterprise infrastructure with verified grounding."
            },
            {
                "slide_id": "slide_2",
                "layout": "cards",
                "kicker": "Core Value",
                "title": "Key Market Pillars",
                "subtitle": "Three core enterprise differentiators.",
                "cards": [
                    {"tag": "Moat", "title": "Platform Advantage", "desc": "High switching costs.", "badge": "Verified"}
                ]
            }
        ]
    }
    mock_bifrost.chat = AsyncMock(return_value=LLMResult(
        text=f"```json\n{json.dumps(mock_llm_json)}\n```",
        model="gemini/gemini-3.5-flash-lite"
    ))

    res = client.post("/api/presentation/create", json={
        "title": "Acme AI — Investor Deck",
        "slide_count": 2,
        "theme": "slate"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Acme AI — Investor Deck"
    assert data["theme"] == "slate"
    assert len(data["slides"]) == 2
    assert data["slides"][0]["title"] == "Acme AI: Autonomous Scalability"
    assert data["slides"][1]["cards"][0]["title"] == "Platform Advantage"


def test_presentation_get_and_put_lifecycle(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    create_res = client.post("/api/presentation/create", json={"title": "Test Deck", "slide_count": 5})
    pres_id = create_res.json()["presentation_id"]

    # GET
    get_res = client.get(f"/api/presentation/{pres_id}")
    assert get_res.status_code == 200
    assert get_res.json()["presentation_id"] == pres_id
    assert len(get_res.json()["slides"]) == 5

    # 404 for unknown ID
    unknown_res = client.get("/api/presentation/unknown_999")
    assert unknown_res.status_code == 404

    # PUT
    deck_data = get_res.json()
    deck_data["title"] = "Updated Deck Title"
    deck_data["theme"] = "coral"
    put_res = client.put(f"/api/presentation/{pres_id}", json={"presentation": deck_data})
    assert put_res.status_code == 200
    assert put_res.json()["title"] == "Updated Deck Title"
    assert put_res.json()["theme"] == "coral"

    # Verify persisted
    refetched = client.get(f"/api/presentation/{pres_id}").json()
    assert refetched["title"] == "Updated Deck Title"
    assert refetched["theme"] == "coral"


def test_presentation_chat_targeted_modification(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container

    # Create initial presentation
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))
    create_res = client.post("/api/presentation/create", json={"title": "Demo Deck", "slide_count": 3})
    pres_id = create_res.json()["presentation_id"]

    # Chat: targeted slide update with LLM delta response
    mock_delta = {
        "operation": "update_slide",
        "target_slide_id": "slide_2",
        "explanation": "Sharpened Slide 2 with recent verified developments and enterprise metrics.",
        "slide": {
            "slide_id": "slide_2",
            "layout": "timeline",
            "kicker": "Recent Velocity",
            "title": "Verified Q3 Developments",
            "subtitle": "Accelerated commercial partnerships.",
            "events": [
                {"date": "Last Month", "title": "Platform Rollout", "desc": "Deployed to enterprise users."}
            ]
        }
    }
    mock_bifrost.chat = AsyncMock(return_value=LLMResult(
        text=json.dumps(mock_delta),
        model="gemini/gemini-3.5-flash-lite"
    ))

    chat_res = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Update slide 2 with recent developments.",
        "selected_slide_index": 1,
        "selected_slide_id": "slide_2"
    })
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["operation_applied"] == "update_slide"
    assert "Sharpened Slide 2" in chat_data["explanation"]

    updated_deck = chat_data["presentation"]
    assert len(updated_deck["slides"]) == 3  # Did NOT wipe or regenerate entire deck!
    assert updated_deck["slides"][0]["slide_id"] == "slide_1"  # Slide 1 unchanged
    assert updated_deck["slides"][1]["title"] == "Verified Q3 Developments"  # Slide 2 updated
    assert updated_deck["slides"][2]["slide_id"] == "slide_3"  # Slide 3 unchanged


def test_presentation_chat_theme_change(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    create_res = client.post("/api/presentation/create", json={"title": "Demo Deck", "slide_count": 3})
    pres_id = create_res.json()["presentation_id"]

    mock_delta = {
        "operation": "update_theme",
        "theme": "editorial",
        "explanation": "Changed presentation theme to Warm Editorial."
    }
    mock_bifrost.chat = AsyncMock(return_value=LLMResult(
        text=json.dumps(mock_delta),
        model="gemini/gemini-3.5-flash-lite"
    ))

    chat_res = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Change theme to editorial",
    })
    assert chat_res.status_code == 200
    assert chat_res.json()["presentation"]["theme"] == "editorial"
    assert chat_res.json()["operation_applied"] == "update_theme"


def test_presentation_chat_deterministic_fallback_when_llm_fails(test_client_and_container):
    client, container, mock_bifrost = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("Gateway Timeout"))

    create_res = client.post("/api/presentation/create", json={"title": "Demo Deck", "slide_count": 3})
    pres_id = create_res.json()["presentation_id"]

    # Even if LLM fails, deterministic fallback safely handles theme switch
    chat_res = client.post("/api/presentation/chat", json={
        "presentation_id": pres_id,
        "message": "Change theme to coral",
    })
    assert chat_res.status_code == 200
    assert chat_res.json()["presentation"]["theme"] == "coral"
    assert chat_res.json()["operation_applied"] == "update_theme"
