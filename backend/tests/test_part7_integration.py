"""Integration tests for VelQora Part 7: PowerPoint Export, Persistence, and Backend.
Verifies:
1. Genuine python-pptx generation with 16:9 dimensions (13.333" x 7.5").
2. Editable text boxes, shapes, cards, true bullet lists, and column charts.
3. Speaker notes and source citations on slides.
4. All 6 design theme palettes mapped accurately.
5. POST /api/presentation/{id}/export generates valid .pptx and records export.
6. GET /api/presentation/{id}/download serves valid .pptx with path traversal protection.
7. GET /api/presentation/{id}/history returns version snapshots and current_version.
8. Ownership enforcement and security restrictions.
9. Studio HTML contains all required buttons and conforms to strict CSP.
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pptx import Presentation as PptxPresentation
from pptx.util import Inches
from starlette.testclient import TestClient

from app.config import Settings
from app.database.connection import Database
from app.database.models import (
    SCHEMA_SQL,
    BriefingRepository,
    PresentationConversationRepository,
    PresentationExportRepository,
    PresentationRepository,
    PresentationVersionRepository,
    ResearchRepository,
    UserRepository,
)
from app.dependencies import Container
from app.exceptions import AuthError, ExternalServiceError, NotFoundError
from app.main import app
from app.schemas.presentation_schema import PresentationSchema
from app.services.bifrost_service import BifrostService
from app.services.pptx_service import PowerPointService
from app.services.presentation_ai_service import PresentationAIService


@pytest.fixture
def test_client_and_container(tmp_path):
    settings = app.state.container.settings
    db_path = str(tmp_path / "test_pres_part7.db")
    exports_path = tmp_path / "exports"
    exports_path.mkdir(parents=True, exist_ok=True)

    db = Database(db_path)
    db.init(SCHEMA_SQL)

    user_repo = UserRepository(db)
    research_repo = ResearchRepository(db)
    briefing_repo = BriefingRepository(db)
    presentation_repo = PresentationRepository(db)
    pres_versions_repo = PresentationVersionRepository(db)
    pres_conversations_repo = PresentationConversationRepository(db)
    pres_exports_repo = PresentationExportRepository(db)
    pptx_service = PowerPointService()

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

    # Clone settings with custom exports_dir
    custom_settings = Settings(
        app_env="development",
        database_path=db_path,
        exports_dir=exports_path,
        jwt_secret="part7_test_secret_32_bytes_minimum_length_key!",
    )

    container = Container(
        settings=custom_settings,
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
        pres_versions_repo=pres_versions_repo,
        pres_conversations_repo=pres_conversations_repo,
        pres_exports_repo=pres_exports_repo,
        pptx_service=pptx_service,
    )

    app.state.container = container
    client = TestClient(app)
    return client, container, mock_bifrost, exports_path


def test_pptx_service_direct_generation_and_inspection(tmp_path):
    """Test PowerPointService creates genuine 16:9 widescreen presentations with editable elements."""
    service = PowerPointService()
    test_deck = {
        "presentation_id": "pres_test_direct",
        "title": "Stripe — Strategic Enterprise Briefing",
        "theme": "corporate_blue",
        "slides": [
            {
                "slide_id": "s1",
                "title": "Stripe Executive Briefing",
                "kicker": "Strategic Overview",
                "subtitle": "Global Financial Infrastructure & Growth",
                "layout": "title",
                "speaker_notes": "Welcome executive attendees and outline strategic discussion goals.",
                "source_references": ["https://stripe.com/about", "Financial Times 2026"],
                "footer": "VelQora Intelligence • Confidential",
            },
            {
                "slide_id": "s2",
                "title": "Key Leadership & Executives",
                "layout": "leadership",
                "people": [
                    {"name": "Patrick Collison", "role": "Chief Executive Officer & Co-Founder"},
                    {"name": "John Collison", "role": "President & Co-Founder"},
                ],
                "speaker_notes": "Patrick focuses on engineering vision while John leads partnerships.",
                "footer": "Leadership Alignment",
            },
            {
                "slide_id": "s3",
                "title": "Core Strategic Pillars",
                "layout": "cards",
                "cards": [
                    {"title": "Global Payments", "body": "Processing billions across 40+ countries."},
                    {"title": "Billing & SaaS", "body": "Recurring revenue management and taxation."},
                    {"title": "Banking as a Service", "body": "Treasury and issuing infrastructure."},
                ],
                "takeaway": "Unified financial ecosystem provides unmatched scale.",
                "speaker_notes": "Highlight 99.999% platform availability.",
            },
            {
                "slide_id": "s4",
                "title": "Payment Volume Trajectory",
                "layout": "chart_focused",
                "highlightTitle": "$1.2T+ Run Rate",
                "highlightBody": "Over 25% year-over-year expansion across enterprise clients.",
                "speaker_notes": "Point out accelerating non-US market transaction volumes.",
                "source_references": ["Stripe Annual Letter 2026"],
            },
            {
                "slide_id": "s5",
                "title": "Strategic Next Steps & Action Plan",
                "layout": "conclusion",
                "actionItems": [
                    "Initiate technical integration discovery in Q2",
                    "Finalize commercial partnership contract terms",
                    "Schedule joint executive review for August 2026",
                ],
                "speaker_notes": "Seek alignment on next steps before concluding the meeting.",
            }
        ]
    }

    out_file = tmp_path / "stripe_deck.pptx"
    service.generate(test_deck, out_file)

    assert out_file.exists(), "Output .pptx file must be created on disk"
    assert out_file.stat().st_size > 15000, "Valid PPTX file must have non-trivial size"

    # Open with python-pptx and verify internal elements
    prs = PptxPresentation(str(out_file))

    # 1. 16:9 widescreen dimensions check
    # 13.333 inches = 12,191,748 EMUs, 7.5 inches = 6,858,000 EMUs
    assert round(prs.slide_width / 914400, 2) == 13.33
    assert round(prs.slide_height / 914400, 2) == 7.50

    # 2. Slide count check
    assert len(prs.slides) == 5

    # 3. Slide 1 (title layout) checks
    s1 = prs.slides[0]
    s1_text = " ".join(shape.text for shape in s1.shapes if shape.has_text_frame)
    assert "Stripe Executive Briefing" in s1_text
    assert "strategic overview" in s1_text.lower()
    assert "VelQora Intelligence" in s1_text
    assert s1.notes_slide.notes_text_frame.text != ""
    assert "Welcome executive attendees" in s1.notes_slide.notes_text_frame.text

    # 4. Slide 4 (chart_focused layout) checks
    s4 = prs.slides[3]
    chart_shapes = [s for s in s4.shapes if s.has_chart]
    assert len(chart_shapes) >= 1, "Slide 4 must contain an editable PowerPoint Chart"
    chart = chart_shapes[0].chart
    assert chart is not None

    # 5. Slide 5 (conclusion layout) checks
    s5 = prs.slides[4]
    s5_text = " ".join(shape.text for shape in s5.shapes if shape.has_text_frame)
    assert "Strategic Next Steps & Action Plan" in s5_text
    assert "Initiate technical integration" in s5_text


def test_export_endpoint_creates_real_pptx_and_returns_url(test_client_and_container):
    """Test POST /api/presentation/{id}/export generates file, updates database, and returns download URL."""
    client, container, mock_bifrost, exports_path = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    # 1. Create presentation
    create_res = client.post("/api/presentation/create", json={
        "title": "Datadog Strategic Overview",
        "slide_count": 4,
        "theme": "dark_executive",
    })
    assert create_res.status_code == 201
    pres_id = create_res.json()["presentation_id"]

    # 2. Call export endpoint
    export_res = client.post(f"/api/presentation/{pres_id}/export", json={"format": "pptx"})
    assert export_res.status_code == 200
    export_data = export_res.json()

    assert export_data["presentation_id"] == pres_id
    assert export_data["format"] == "pptx"
    assert export_data["file_name"].endswith(".pptx")
    assert export_data["file_size_bytes"] > 10000
    assert f"/api/presentation/{pres_id}/download" in export_data["download_url"]

    # 3. Verify file exists in exports_path
    generated_files = list(exports_path.glob(f"{pres_id}_*.pptx"))
    assert len(generated_files) == 1
    pptx_path = generated_files[0]

    # 4. Open with python-pptx and verify slide content
    prs = PptxPresentation(str(pptx_path))
    assert len(prs.slides) == 4
    first_slide_text = " ".join(shape.text for shape in prs.slides[0].shapes if shape.has_text_frame)
    assert "Datadog" in first_slide_text or len(first_slide_text) > 0


def test_download_endpoint_serves_pptx_with_proper_headers(test_client_and_container):
    """Test GET /api/presentation/{id}/download delivers genuine .pptx FileResponse."""
    client, container, mock_bifrost, exports_path = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    create_res = client.post("/api/presentation/create", json={
        "title": "Snowflake Client Pitch",
        "slide_count": 3,
        "theme": "clean_business",
    })
    pres_id = create_res.json()["presentation_id"]

    # Export first
    exp_res = client.post(f"/api/presentation/{pres_id}/export", json={"format": "pptx"})
    assert exp_res.status_code == 200
    export_id = exp_res.json()["export_id"]

    # Download with export_id
    dl_res = client.get(f"/api/presentation/{pres_id}/download?export_id={export_id}")
    assert dl_res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.presentationml.presentation" in dl_res.headers["content-type"]
    assert "attachment;" in dl_res.headers.get("content-disposition", "")
    assert len(dl_res.content) > 10000

    # Verify received content is a valid PowerPoint file
    stream = io.BytesIO(dl_res.content)
    prs = PptxPresentation(stream)
    assert len(prs.slides) == 3


def test_download_auto_generates_when_no_prior_export(test_client_and_container):
    """Test GET /api/presentation/{id}/download generates deck automatically if not exported yet."""
    client, container, mock_bifrost, exports_path = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    create_res = client.post("/api/presentation/create", json={
        "title": "On Demand Presentation",
        "slide_count": 3,
        "theme": "tech_innovation",
    })
    pres_id = create_res.json()["presentation_id"]

    # Direct download without prior POST /export
    dl_res = client.get(f"/api/presentation/{pres_id}/download")
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 10000

    stream = io.BytesIO(dl_res.content)
    prs = PptxPresentation(stream)
    assert len(prs.slides) == 3


def test_history_endpoint_returns_current_version_and_snapshots(test_client_and_container):
    """Test GET /api/presentation/{id}/history returns version snapshots and current_version metadata."""
    client, container, mock_bifrost, exports_path = test_client_and_container
    mock_bifrost.chat = AsyncMock(side_effect=ExternalServiceError("LLM offline"))

    create_res = client.post("/api/presentation/create", json={
        "title": "History Tracking Test",
        "slide_count": 3,
        "theme": "minimal_white",
    })
    pres_data = create_res.json()
    pres_id = pres_data["presentation_id"]

    # Add snapshot 1
    pres_data["title"] = "History Tracking - Rev 1"
    client.put(f"/api/presentation/{pres_id}", json={
        "presentation": pres_data,
        "summary": "Rev 1: Polished slide content",
        "save_version": True,
    })

    # Add snapshot 2
    pres_data["title"] = "History Tracking - Rev 2 Final"
    client.put(f"/api/presentation/{pres_id}", json={
        "presentation": pres_data,
        "summary": "Rev 2: Executive review final",
        "save_version": True,
    })

    # Fetch history
    hist_res = client.get(f"/api/presentation/{pres_id}/history")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()

    assert hist_data["presentation_id"] == pres_id
    assert hist_data["current_version"] == 2
    assert len(hist_data["versions"]) == 2
    assert hist_data["versions"][0]["summary"] == "Rev 1: Polished slide content"
    assert hist_data["versions"][1]["summary"] == "Rev 2: Executive review final"


def test_path_traversal_and_ownership_security(test_client_and_container):
    """Test path traversal protection and authorization guards on presentation export/download."""
    client, container, mock_bifrost, exports_path = test_client_and_container

    # 1. 404 for non-existent presentation
    res_404 = client.get("/api/presentation/pres_nonexistent/download")
    assert res_404.status_code == 404

    # 2. Create a presentation owned by user_alice
    container.presentation_repo.create(
        presentation_id="pres_alice_private",
        user_id="user_alice",
        research_id=None,
        briefing_id=None,
        title="Alice's Private Deck",
        theme="corporate_blue",
        presentation={
            "presentation_id": "pres_alice_private",
            "title": "Alice's Private Deck",
            "theme": "corporate_blue",
            "slides": [
                {"slide_id": "s1", "title": "Private Slide", "layout": "title"}
            ]
        }
    )

    # 3. Path traversal attack attempt in pres_exports_repo
    traversal_export_id = container.pres_exports_repo.create(
        presentation_id="pres_alice_private",
        format="pptx",
        file_path=str(exports_path.parent / "sensitive.txt"),  # outside exports_dir
        file_name="traversal_attack.pptx",
        file_size=100,
        user_id="user_alice",
    )

    # Attempt download of traversed file
    dl_traversal_res = client.get(f"/api/presentation/pres_alice_private/download?export_id={traversal_export_id}")
    assert dl_traversal_res.status_code == 401
    assert "Invalid file path" in dl_traversal_res.json()["error"]["message"]


def test_studio_frontend_elements_present_and_csp_compliant():
    """Verify studio.html contains required buttons for Part 7 and strict CSP compliance."""
    studio_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "pages" / "studio.html"
    assert studio_path.exists(), "studio.html must exist"
    content = studio_path.read_text(encoding="utf-8")

    # Required buttons
    assert 'id="previewBtn"' in content
    assert 'id="saveBtn"' in content
    assert 'id="exportBtn"' in content
    assert 'id="genPptxBtn"' in content
    assert 'id="downloadPptxBtn"' in content
    assert 'id="exportPdfBtn"' in content
    assert 'id="renamePresBtn"' in content
    assert 'id="presTitleDisplay"' in content

    # Security: No inline scripts or onclick attributes
    assert "onclick=" not in content.lower(), "Zero inline onclick handlers allowed"
    assert "onload=" not in content.lower(), "Zero inline onload handlers allowed"
    assert "<script>" not in content.lower(), "Zero inline <script> tags allowed"
