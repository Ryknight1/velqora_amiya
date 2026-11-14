"""Integration tests for VelQora Part 4: AI Presentation Studio UI."""
import re
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.main import app

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


def test_studio_page_loads_and_assets_return_200():
    client = TestClient(app)
    res = client.get("/pages/studio.html")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.text

    # Extract all CSS links
    css_hrefs = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']', html)
    for href in css_hrefs:
        if href.startswith("http"):
            continue
        clean_path = href.replace("../", "/")
        asset_res = client.get(clean_path)
        assert asset_res.status_code == 200, f"Failed to load CSS asset: {href} ({clean_path})"

    # Extract all JS script tags
    js_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
    for src in js_srcs:
        if src.startswith("http"):
            continue
        clean_path = src.replace("../", "/")
        asset_res = client.get(clean_path)
        assert asset_res.status_code == 200, f"Failed to load JS asset: {src} ({clean_path})"


def test_studio_page_heading_and_three_panel_structure():
    client = TestClient(app)
    res = client.get("/pages/studio.html")
    html = res.text

    # Heading & description
    assert "Make Your Meeting Presentation" in html
    assert "Turn your research into a presentation that makes every conversation count." in html

    # Three-panel structure
    assert 'id="chatPanel"' in html, "Missing left chat panel"
    assert 'id="editorPanel"' in html, "Missing center editor panel"
    assert 'id="navPanel"' in html, "Missing right slide navigator panel"

    # VelQora AI Branding in Chat Panel
    assert "VelQora AI" in html
    assert 'id="chatLog"' in html
    assert 'id="chatForm"' in html
    assert 'id="chatInput"' in html
    assert 'id="sendBtn"' in html
    assert 'id="chatTyping"' in html
    assert 'id="regenBtn"' in html
    assert 'id="promptRow"' in html

    # Slide Editor in Center Panel
    assert 'id="slideCanvas"' in html
    assert 'id="slideCanvasContainer"' in html
    assert 'id="slideLabel"' in html

    # Slide Navigator in Right Panel
    assert 'id="thumbList"' in html
    assert 'id="slideCountLabel"' in html
    assert 'id="navAddSlideBtn"' in html
    assert 'id="navDupSlideBtn"' in html
    assert 'id="navDelSlideBtn"' in html


def test_studio_toolbar_controls():
    client = TestClient(app)
    res = client.get("/pages/studio.html")
    html = res.text

    # Required Toolbar items: Undo, Redo, Theme, Add Slide, Preview, Save, Export
    assert 'id="undoBtn"' in html, "Missing Undo button"
    assert 'id="redoBtn"' in html, "Missing Redo button"
    assert 'id="themeBtn"' in html, "Missing Theme button"
    assert 'id="addSlideBtn"' in html, "Missing Add Slide button"
    assert 'id="previewBtn"' in html, "Missing Preview button"
    assert 'id="saveBtn"' in html, "Missing Save button"
    assert 'id="exportBtn"' in html, "Missing Export button"
    assert 'id="configBtn"' in html, "Missing Setup button"


def test_studio_presentation_configuration_modal():
    client = TestClient(app)
    res = client.get("/pages/studio.html")
    html = res.text

    # Setup modal exists
    assert 'id="configModal"' in html
    assert "Presentation Setup" in html

    # Required 9 fields
    assert 'id="cfgPresTitle"' in html, "Missing Presentation Title input"
    assert 'id="cfgSlideCount"' in html, "Missing Number of Slides select"
    assert 'id="cfgAudience"' in html, "Missing Audience select"
    assert 'id="cfgMeetingPurpose"' in html, "Missing Meeting Purpose input"
    assert 'id="cfgTone"' in html, "Missing Tone select"
    assert 'id="cfgTheme"' in html, "Missing Design Theme select"
    assert 'id="cfgDetail"' in html, "Missing Level of Detail select"
    assert 'name="cfgTopics"' in html, "Missing Topics to Include"
    assert 'name="cfgExclude"' in html, "Missing Topics to Exclude"


def test_studio_javascript_modules_and_prompts():
    state_file = FRONTEND_DIR / "assets" / "js" / "presentation-state.js"
    renderer_file = FRONTEND_DIR / "assets" / "js" / "slide-renderer.js"
    studio_file = FRONTEND_DIR / "assets" / "js" / "studio.js"

    assert state_file.is_file(), "presentation-state.js must exist"
    assert renderer_file.is_file(), "slide-renderer.js must exist"
    assert studio_file.is_file(), "studio.js must exist"

    state_code = state_file.read_text(encoding="utf-8")
    assert "class PresentationState" in state_code
    assert "undo(" in state_code
    assert "redo(" in state_code
    assert "addSlide(" in state_code
    assert "duplicateSlide(" in state_code
    assert "deleteSlide(" in state_code
    assert "moveSlide(" in state_code
    assert "setTheme(" in state_code
    assert "saveToStorage(" in state_code
    assert "exportJSON(" in state_code
    assert "exportMarkdown(" in state_code

    renderer_code = renderer_file.read_text(encoding="utf-8")
    assert "class SlideRenderer" in renderer_code
    assert "renderCanvas" in renderer_code
    assert "renderThumbnail" in renderer_code
    assert "renderPreview" in renderer_code
    for layout in ["title", "cards", "split", "metrics", "timeline", "leadership", "conclusion"]:
      assert layout in renderer_code, f"Layout {layout} missing from renderer"

    studio_code = studio_file.read_text(encoding="utf-8")
    # All 7 suggested prompts
    required_prompts = [
        "Create a 7-slide presentation.",
        "Make this presentation more professional.",
        "Improve slide 3.",
        "Add recent company developments.",
        "Add leadership information.",
        "Create a conclusion slide.",
        "Change presentation theme."
    ]
    for prompt in required_prompts:
        assert prompt in studio_code, f"Prompt '{prompt}' missing from studio.js"


def test_studio_csp_compliance_no_inline_scripts():
    html_file = FRONTEND_DIR / "pages" / "studio.html"
    html = html_file.read_text(encoding="utf-8")

    # Ensure no inline <script> tags with executable code
    script_tags = re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", html, re.DOTALL)
    for tag_content in script_tags:
        assert not tag_content.strip(), f"Inline script found in studio.html: {tag_content}"

    # Ensure no inline event handlers (e.g. onclick, onchange, etc.)
    inline_handlers = re.findall(r'\s(on[a-z]+)=["\'][^"\']+["\']', html, re.IGNORECASE)
    assert len(inline_handlers) == 0, f"Inline event handlers found in studio.html: {inline_handlers}"
