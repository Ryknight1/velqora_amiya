"""Comprehensive Performance, Stability, and Reliability Audit Tests for VelQora."""
import json
import re
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.database.connection import Database
from app.database.models import PresentationRepository
from app.main import app

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


# =====================================================================
# 1. FRONTEND ARCHITECTURE & EVENT LISTENER AUDIT
# =====================================================================

def test_mobile_hamburger_menu_has_single_owner():
    """Verify that app.js does not add a duplicate click listener to #burger, which broke mobile menu."""
    app_js_path = FRONTEND_DIR / "assets" / "js" / "app.js"
    assert app_js_path.exists()
    app_js = app_js_path.read_text(encoding="utf-8")

    # In app.js, lines duplicate-binding #burger should be removed so nav.js handles it cleanly
    assert 'burger.addEventListener("click"' not in app_js, "app.js must not add duplicate click listener to #burger"

    # nav.js should be the single source of truth for mobile navigation
    nav_js_path = FRONTEND_DIR / "assets" / "js" / "nav.js"
    assert nav_js_path.exists()
    nav_js = nav_js_path.read_text(encoding="utf-8")
    assert 'burger.addEventListener("click"' in nav_js
    assert 'aria-expanded' in nav_js


def test_scroll_and_spotlight_throttled_with_raf():
    """Verify that high-frequency scroll and pointer events in app.js are throttled with requestAnimationFrame."""
    app_js = (FRONTEND_DIR / "assets" / "js" / "app.js").read_text(encoding="utf-8")
    assert "requestAnimationFrame" in app_js
    assert "scrollTicking" in app_js or "updateScroll" in app_js


def test_api_client_handles_file_protocol_and_401_signout():
    """Verify that api.js safely falls back when opened via file: and clears stale tokens on 401."""
    api_js = (FRONTEND_DIR / "assets" / "js" / "api.js").read_text(encoding="utf-8")
    assert "protocol" in api_js and "file:" in api_js, "api.js should handle file: protocol gracefully"
    assert "VQAuth.signOut()" in api_js, "api.js should call VQAuth.signOut() on 401 Unauthorized"


def test_polling_loops_exit_immediately_on_failure():
    """Verify intelligence.js and meeting.js do not poll 45 times when a briefing has failed."""
    intel_js = (FRONTEND_DIR / "assets" / "js" / "intelligence.js").read_text(encoding="utf-8")
    assert 'b.status === "failed"' in intel_js

    meet_js = (FRONTEND_DIR / "assets" / "js" / "meeting.js").read_text(encoding="utf-8")
    assert 'b.status === "failed"' in meet_js


def test_studio_concurrency_guards_and_escape_key():
    """Verify Presentation Studio has double-click protection and modal Escape key listener."""
    studio_js = (FRONTEND_DIR / "assets" / "js" / "studio.js").read_text(encoding="utf-8")
    assert "isPromptRunning" in studio_js, "studio.js should guard against concurrent prompt execution"
    assert "if (!presentationState || isSaving) return;" in studio_js, "saveToBackend should guard against concurrent saves"
    assert 'e.key === "Escape"' in studio_js


def test_global_css_prevents_horizontal_overflow():
    """Verify global.css and responsive.css prevent horizontal overflow across devices."""
    global_css = (FRONTEND_DIR / "assets" / "css" / "global.css").read_text(encoding="utf-8")
    assert "overflow-x:hidden" in global_css or "overflow-x: hidden" in global_css

    resp_css = (FRONTEND_DIR / "assets" / "css" / "responsive.css").read_text(encoding="utf-8")
    assert "max-width:480px" in resp_css or "max-width: 480px" in resp_css


# =====================================================================
# 2. BACKEND DATABASE CONCURRENCY & CONNECTION SAFETY
# =====================================================================

def test_database_connection_sets_busy_timeout_and_foreign_keys(tmp_path):
    """Verify that SQLite connections configure busy_timeout and foreign_keys."""
    db_path = str(tmp_path / "test_concurrency.db")
    db = Database(db_path)
    db.init("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT);")

    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout;")
        busy_timeout = cursor.fetchone()[0]
        assert busy_timeout >= 10000, f"Expected busy_timeout >= 10000ms, got {busy_timeout}"

        cursor.execute("PRAGMA foreign_keys;")
        foreign_keys = cursor.fetchone()[0]
        assert foreign_keys == 1, "Expected foreign_keys = 1 (ON)"


def test_cors_methods_support_delete_and_head():
    """Verify CORS configuration supports standard HTTP methods including DELETE and HEAD."""
    client = TestClient(app)
    res = client.options("/api/presentation/pres_dummy", headers={
        "Origin": "http://localhost:5500",
        "Access-Control-Request-Method": "PUT",
    })
    assert res.status_code == 200
    allow_methods = res.headers.get("access-control-allow-methods", "")
    assert "PUT" in allow_methods
    assert "DELETE" in allow_methods
    assert "HEAD" in allow_methods


# =====================================================================
# 3. COMPLETE USER JOURNEY VERIFICATION & ERROR HANDLING
# =====================================================================

def test_complete_frontend_page_links_validity():
    """Verify that all internal HTML links point to existing pages and no broken links exist."""
    pages_dir = FRONTEND_DIR / "pages"
    html_files = list(pages_dir.glob("*.html"))
    assert len(html_files) >= 5, "Expected at least 5 main HTML pages"

    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8")
        # Find all href="something.html"
        hrefs = re.findall(r'href=["\']([^"\']+\.html(?:#[^"\']*)?)["\']', content)
        for href in hrefs:
            clean_href = href.split("?")[0].split("#")[0]
            target_file = pages_dir / clean_href
            assert target_file.exists(), f"Broken link '{href}' found in {html_file.name}"


def test_invalid_presentation_history_and_export_error_handling():
    """Verify predictable error responses on invalid IDs and requests."""
    client = TestClient(app)

    # 1. Non-existent presentation returns 404
    res = client.get("/api/presentation/pres_nonexistent_12345")
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "not_found"

    # 2. Non-existent history returns 404
    res = client.get("/api/presentation/pres_nonexistent_12345/history")
    assert res.status_code == 404

    # 3. Export non-existent presentation returns 404
    res = client.post("/api/presentation/pres_nonexistent_12345/export", json={"format": "pptx"})
    assert res.status_code == 404

    # 4. Download non-existent presentation returns 404
    res = client.get("/api/presentation/pres_nonexistent_12345/download")
    assert res.status_code == 404


def test_rapid_concurrent_save_and_update_lifecycle():
    """Verify rapid presentation updates do not corrupt data or raise lock errors."""
    client = TestClient(app)

    # 1. Create a presentation
    create_res = client.post("/api/presentation/create", json={
        "title": "Performance Audit Presentation",
        "slide_count": 3,
        "theme": "corporate_blue"
    })
    assert create_res.status_code == 201
    deck = create_res.json()
    pres_id = deck.get("presentation_id") or deck.get("id")
    assert pres_id is not None

    # 2. Rapid updates
    for i in range(5):
        deck["title"] = f"Performance Audit Presentation v{i+1}"
        put_res = client.put(f"/api/presentation/{pres_id}", json={
            "presentation": deck,
            "summary": f"Iteration {i+1}",
            "save_version": True
        })
        assert put_res.status_code == 200

    # 3. Verify history integrity
    hist_res = client.get(f"/api/presentation/{pres_id}/history")
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert len(hist["versions"]) >= 5
    assert hist["presentation_id"] == pres_id
