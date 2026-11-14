"""Unit and integration tests for the Presentation Studio Mobile Layout improvements."""
import re
from pathlib import Path
from starlette.testclient import TestClient

from app.main import app

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


def test_studio_mobile_toolbar_buttons_and_icons():
    """Verify all 9 toolbar buttons and 3 switcher tabs have appropriate IDs and SVG icons."""
    client = TestClient(app)
    res = client.get("/pages/studio.html")
    assert res.status_code == 200
    html = res.text

    # 1. Verify 9 toolbar buttons with exact IDs
    expected_button_ids = [
        "undoBtn",
        "redoBtn",
        "themeBtn",
        "addSlideBtn",
        "configBtn",
        "historyBtn",
        "previewBtn",
        "saveBtn",
        "exportBtn",
    ]
    for btn_id in expected_button_ids:
        assert f'id="{btn_id}"' in html, f"Missing toolbar button id: {btn_id}"

    # 2. Verify all 9 buttons contain SVG icons
    toolbar_actions_match = re.search(r'<div class="studio-actions">(.*?)</div>\s*<!-- Mobile View Switcher Tabs -->', html, re.DOTALL)
    assert toolbar_actions_match is not None, "Could not find .studio-actions block"
    toolbar_html = toolbar_actions_match.group(1)

    svg_icons = re.findall(r'<svg class="btn-icon"[^>]*>', toolbar_html)
    assert len(svg_icons) == 9, f"Expected 9 SVG icons in toolbar, found {len(svg_icons)}"

    # 3. Verify Theme button preserves #themeDot and #themeBtnLabel
    theme_btn_match = re.search(r'<button[^>]+id="themeBtn"[^>]*>(.*?)</button>', html, re.DOTALL)
    assert theme_btn_match is not None
    assert 'id="themeDot"' in theme_btn_match.group(1)
    assert 'id="themeBtnLabel"' in theme_btn_match.group(1)

    # 4. Verify 3 switcher tabs have icons and preserve #mobileSlideCount
    tabs_match = re.search(r'<div class="studio-tabs"[^>]*>(.*?)</div>', html, re.DOTALL)
    assert tabs_match is not None
    tabs_html = tabs_match.group(1)

    tab_icons = re.findall(r'<svg class="tab-icon"[^>]*>', tabs_html)
    assert len(tab_icons) == 3, f"Expected 3 tab icons, found {len(tab_icons)}"
    assert 'data-panel="chatPanel"' in tabs_html
    assert 'data-panel="editorPanel"' in tabs_html
    assert 'data-panel="navPanel"' in tabs_html
    assert 'id="mobileSlideCount"' in tabs_html

    # 5. Verify status badges are kept and live in header meta
    assert 'id="savedBadge"' in html
    assert 'id="dirtyFlag"' in html
    assert 'class="studio-head-meta"' in html


def test_studio_css_mobile_rules_and_3column_grid():
    """Verify CSS has 3-column grid, compact heights, and page-lead hidden on mobile."""
    css_path = FRONTEND_DIR / "assets" / "css" / "studio.css"
    assert css_path.exists(), "studio.css does not exist"
    css_text = css_path.read_text(encoding="utf-8")

    # 1. 3-column responsive grid on mobile
    assert "grid-template-columns: repeat(3, 1fr)" in css_text

    # 2. page-lead hidden on mobile to bring Chatbot higher
    mobile_media_match = re.search(r'@media\s*\(max-width:\s*680px\)\s*\{(.*?)\n\}', css_text, re.DOTALL)
    assert mobile_media_match is not None, "Missing @media (max-width: 680px) in studio.css"
    mobile_css = mobile_media_match.group(1)

    assert "display: none" in mobile_css and "page-lead" in mobile_css

    # 3. Compact button heights (32px) and border radius (7-8px)
    assert "height: 32px" in mobile_css
    assert "border-radius: 7px" in mobile_css or "border-radius: 8px" in mobile_css

    # 4. Save and Export visual hierarchy accents
    assert ".btn-save-action" in css_text
    assert ".btn-export-action" in css_text
