"""VelQora PowerPoint (.pptx) Presentation Generation Service.
Generates genuine, editable 16:9 widescreen PowerPoint decks with semantic
shapes, headings, text boxes, bullet lists, charts, speaker notes, and theme palettes.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pptx import Presentation as PPTXPresentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from ..schemas.presentation_schema import PresentationSchema, SlideSchema

logger = logging.getLogger("velqora.pptx")

# 16:9 widescreen slide dimensions in inches
SLIDE_WIDTH_INCHES = 13.333
SLIDE_HEIGHT_INCHES = 7.5

# Theme color definitions
THEME_PALETTES: Dict[str, Dict[str, RGBColor]] = {
    "corporate_blue": {
        "bg": RGBColor(11, 30, 63),
        "primary": RGBColor(30, 64, 175),
        "secondary": RGBColor(59, 130, 246),
        "accent": RGBColor(255, 88, 88),
        "text": RGBColor(255, 255, 255),
        "muted": RGBColor(200, 215, 235),
        "card_bg": RGBColor(18, 42, 82),
        "card_border": RGBColor(45, 75, 125),
    },
    "minimal_white": {
        "bg": RGBColor(255, 255, 255),
        "primary": RGBColor(15, 23, 42),
        "secondary": RGBColor(71, 85, 105),
        "accent": RGBColor(37, 99, 235),
        "text": RGBColor(15, 23, 42),
        "muted": RGBColor(100, 116, 139),
        "card_bg": RGBColor(248, 250, 252),
        "card_border": RGBColor(226, 232, 240),
    },
    "dark_executive": {
        "bg": RGBColor(16, 20, 29),
        "primary": RGBColor(30, 41, 59),
        "secondary": RGBColor(51, 65, 85),
        "accent": RGBColor(255, 88, 88),
        "text": RGBColor(248, 250, 252),
        "muted": RGBColor(180, 195, 210),
        "card_bg": RGBColor(26, 33, 48),
        "card_border": RGBColor(75, 45, 55),
    },
    "modern_gradient": {
        "bg": RGBColor(30, 27, 75),
        "primary": RGBColor(99, 102, 241),
        "secondary": RGBColor(139, 92, 246),
        "accent": RGBColor(236, 72, 153),
        "text": RGBColor(255, 255, 255),
        "muted": RGBColor(220, 215, 245),
        "card_bg": RGBColor(45, 22, 75),
        "card_border": RGBColor(120, 45, 120),
    },
    "clean_business": {
        "bg": RGBColor(241, 245, 249),
        "primary": RGBColor(30, 41, 59),
        "secondary": RGBColor(2, 132, 199),
        "accent": RGBColor(13, 148, 136),
        "text": RGBColor(15, 23, 42),
        "muted": RGBColor(71, 85, 105),
        "card_bg": RGBColor(255, 255, 255),
        "card_border": RGBColor(203, 213, 225),
    },
    "tech_innovation": {
        "bg": RGBColor(3, 7, 18),
        "primary": RGBColor(11, 19, 43),
        "secondary": RGBColor(16, 185, 129),
        "accent": RGBColor(6, 182, 212),
        "text": RGBColor(240, 253, 250),
        "muted": RGBColor(160, 210, 215),
        "card_bg": RGBColor(11, 25, 48),
        "card_border": RGBColor(15, 75, 100),
    },
}

# Theme aliases for backward compatibility
THEME_ALIASES: Dict[str, str] = {
    "navy": "corporate_blue",
    "light": "minimal_white",
    "coral": "dark_executive",
    "gradient": "modern_gradient",
    "editorial": "clean_business",
    "slate": "tech_innovation",
}


class PowerPointService:
    """Generates editable PowerPoint presentations (.pptx) from presentation schema."""

    @classmethod
    def get_palette(cls, theme_name: Optional[str]) -> Dict[str, RGBColor]:
        t = (theme_name or "corporate_blue").lower()
        resolved = THEME_ALIASES.get(t, t)
        return THEME_PALETTES.get(resolved, THEME_PALETTES["corporate_blue"])

    @classmethod
    def _pct_x(cls, pct: float) -> Inches:
        return Inches(SLIDE_WIDTH_INCHES * (max(0.0, min(100.0, pct)) / 100.0))

    @classmethod
    def _pct_y(cls, pct: float) -> Inches:
        return Inches(SLIDE_HEIGHT_INCHES * (max(0.0, min(100.0, pct)) / 100.0))

    @classmethod
    def _pct_w(cls, pct: float) -> Inches:
        return Inches(SLIDE_WIDTH_INCHES * (max(0.0, min(100.0, pct)) / 100.0))

    @classmethod
    def _pct_h(cls, pct: float) -> Inches:
        return Inches(SLIDE_HEIGHT_INCHES * (max(0.0, min(100.0, pct)) / 100.0))

    @classmethod
    def generate(cls, presentation: PresentationSchema | dict, output_path: str | Path) -> Path:
        """Create a complete, high-quality, editable PowerPoint deck."""
        if isinstance(presentation, dict):
            presentation = PresentationSchema.model_validate(presentation)

        prs = PPTXPresentation()
        prs.slide_width = Inches(SLIDE_WIDTH_INCHES)
        prs.slide_height = Inches(SLIDE_HEIGHT_INCHES)

        palette = cls.get_palette(presentation.theme)
        blank_layout = prs.slide_layouts[6]

        slides_data = presentation.slides or []
        for idx, slide_model in enumerate(slides_data):
            slide_dict = slide_model.model_dump()
            slide = prs.slides.add_slide(blank_layout)

            # 1. Slide Solid Background
            bg = slide.background
            fill = bg.fill
            fill.solid()
            fill.fore_color.rgb = palette["bg"]

            layout = slide_dict.get("layout", "cards")

            # 2. Header (Kicker, Title, Subtitle)
            cls._add_slide_header(slide, slide_dict, palette, is_title_slide=(layout == "title"))

            # 3. Layout-Specific Content
            if layout == "title":
                cls._build_title_slide(slide, slide_dict, palette)
            elif layout in ("split", "two_column"):
                cls._build_split_slide(slide, slide_dict, palette)
            elif layout in ("metrics", "statistics_dashboard"):
                cls._build_metrics_slide(slide, slide_dict, palette)
            elif layout == "timeline":
                cls._build_timeline_slide(slide, slide_dict, palette)
            elif layout == "leadership":
                cls._build_leadership_slide(slide, slide_dict, palette)
            elif layout == "conclusion":
                cls._build_conclusion_slide(slide, slide_dict, palette)
            elif layout == "comparison":
                cls._build_comparison_slide(slide, slide_dict, palette)
            elif layout == "chart_focused":
                cls._build_chart_slide(slide, slide_dict, palette)
            else:  # cards or default
                cls._build_cards_slide(slide, slide_dict, palette)

            # 4. Custom Added Elements (if any)
            cls._add_custom_elements(slide, slide_dict.get("customElements") or [], palette)

            # 5. Footer & Grounding Reference
            cls._add_slide_footer(slide, slide_dict, palette, presentation.title)

            # 6. Speaker Notes
            cls._add_speaker_notes(slide, slide_dict)

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(out_file))

        if not out_file.exists() or out_file.stat().st_size == 0:
            raise RuntimeError(f"PowerPoint generation failed: {out_file} is empty or missing.")

        logger.info("Successfully generated PowerPoint presentation at %s (%d bytes, %d slides)",
                    out_file, out_file.stat().st_size, len(slides_data))
        return out_file

    @classmethod
    def _add_slide_header(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor], is_title_slide: bool) -> None:
        if is_title_slide:
            return  # Title slide has its own center-staged header layout

        kicker = slide_dict.get("kicker")
        title = slide_dict.get("title") or "Meeting Presentation Slide"
        subtitle = slide_dict.get("subtitle")

        # Kicker
        if kicker:
            tb = slide.shapes.add_textbox(cls._pct_x(6.0), cls._pct_y(6.5), cls._pct_w(88.0), cls._pct_h(4.5))
            tf = tb.text_frame
            tf.word_wrap = True
            tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
            p = tf.paragraphs[0]
            p.text = kicker.upper()
            p.font.size = Pt(11)
            p.font.bold = True
            p.font.color.rgb = palette["accent"]

        # Title
        title_y = 11.5 if kicker else 7.5
        tb_title = slide.shapes.add_textbox(cls._pct_x(6.0), cls._pct_y(title_y), cls._pct_w(88.0), cls._pct_h(10.0))
        tf_title = tb_title.text_frame
        tf_title.word_wrap = True
        tf_title.margin_left = tf_title.margin_top = tf_title.margin_right = tf_title.margin_bottom = 0
        p_title = tf_title.paragraphs[0]
        p_title.text = title
        p_title.font.size = Pt(26)
        p_title.font.bold = True
        p_title.font.color.rgb = palette["text"]

        # Subtitle
        if subtitle:
            sub_y = title_y + 10.0
            tb_sub = slide.shapes.add_textbox(cls._pct_x(6.0), cls._pct_y(sub_y), cls._pct_w(88.0), cls._pct_h(7.0))
            tf_sub = tb_sub.text_frame
            tf_sub.word_wrap = True
            tf_sub.margin_left = tf_sub.margin_top = tf_sub.margin_right = tf_sub.margin_bottom = 0
            p_sub = tf_sub.paragraphs[0]
            p_sub.text = subtitle
            p_sub.font.size = Pt(13)
            p_sub.font.color.rgb = palette["muted"]

    @classmethod
    def _build_title_slide(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor]) -> None:
        kicker = slide_dict.get("kicker") or "EXECUTIVE BRIEFING"
        title = slide_dict.get("title") or "Meeting Strategic Briefing"
        subtitle = slide_dict.get("subtitle") or "Prepared with verified source intelligence and data."

        # Kicker Pill shape
        pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cls._pct_x(6.0), cls._pct_y(22.0), cls._pct_w(28.0), cls._pct_h(5.5))
        pill.fill.solid()
        pill.fill.fore_color.rgb = palette["card_bg"]
        pill.line.color.rgb = palette["accent"]
        pill.line.width = Pt(1.5)
        p_tf = pill.text_frame
        p_tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = p_tf.paragraphs[0]
        p.text = kicker.upper()
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = palette["accent"]
        p.alignment = PP_ALIGN.CENTER

        # Main Title
        tb_title = slide.shapes.add_textbox(cls._pct_x(6.0), cls._pct_y(32.0), cls._pct_w(88.0), cls._pct_h(22.0))
        tf_title = tb_title.text_frame
        tf_title.word_wrap = True
        p_title = tf_title.paragraphs[0]
        p_title.text = title
        p_title.font.size = Pt(40)
        p_title.font.bold = True
        p_title.font.color.rgb = palette["text"]

        # Subtitle
        tb_sub = slide.shapes.add_textbox(cls._pct_x(6.0), cls._pct_y(56.0), cls._pct_w(80.0), cls._pct_h(12.0))
        tf_sub = tb_sub.text_frame
        tf_sub.word_wrap = True
        p_sub = tf_sub.paragraphs[0]
        p_sub.text = subtitle
        p_sub.font.size = Pt(16)
        p_sub.font.color.rgb = palette["muted"]

    @classmethod
    def _build_cards_slide(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor]) -> None:
        cards = slide_dict.get("cards") or [
            {"tag": "Focus 01", "title": "Strategic Foundation", "desc": "Key operational highlights and core capabilities."},
            {"tag": "Focus 02", "title": "Market Velocity", "desc": "Validated traction and acceleration across primary targets."},
            {"tag": "Focus 03", "title": "Partnership Moat", "desc": "Commercial alignment and high bilateral synergies."},
        ]
        count = min(3, len(cards))
        if count == 0:
            return

        w_pct = 26.5
        gap_pct = 4.0
        start_x = 6.0
        y_pct = 38.0
        h_pct = 46.0

        for i, card in enumerate(cards[:count]):
            x_pct = start_x + i * (w_pct + gap_pct)

            # Card shape
            shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                cls._pct_x(x_pct), cls._pct_y(y_pct),
                cls._pct_w(w_pct), cls._pct_h(h_pct)
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = palette["card_bg"]
            shape.line.color.rgb = palette["card_border"]
            shape.line.width = Pt(1)

            # Card Text Box inside shape
            tb = slide.shapes.add_textbox(
                cls._pct_x(x_pct + 1.5), cls._pct_y(y_pct + 2.0),
                cls._pct_w(w_pct - 3.0), cls._pct_h(h_pct - 4.0)
            )
            tf = tb.text_frame
            tf.word_wrap = True

            # Tag
            p_tag = tf.paragraphs[0]
            p_tag.text = (card.get("tag") or card.get("badge") or f"Pillar 0{i+1}").upper()
            p_tag.font.size = Pt(10)
            p_tag.font.bold = True
            p_tag.font.color.rgb = palette["accent"]
            p_tag.space_after = Pt(8)

            # Title
            p_t = tf.add_paragraph()
            p_t.text = card.get("title") or "Key Strategic Insight"
            p_t.font.size = Pt(16)
            p_t.font.bold = True
            p_t.font.color.rgb = palette["text"]
            p_t.space_after = Pt(8)

            # Description
            p_d = tf.add_paragraph()
            p_d.text = card.get("desc") or ""
            p_d.font.size = Pt(12)
            p_d.font.color.rgb = palette["muted"]

    @classmethod
    def _build_split_slide(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor]) -> None:
        bullets = slide_dict.get("bullets") or [
            "Validated core market differentiation and enterprise stability.",
            "Accelerating commercial traction across target verticals.",
            "High bilateral alignment on immediate strategic priorities."
        ]
        highlight_title = slide_dict.get("highlightTitle") or "Strategic Takeaway"
        highlight_body = slide_dict.get("highlightBody") or slide_dict.get("takeaway") or "Immediate bilateral value alignment."

        # Left Column: Bullets
        tb_bullets = slide.shapes.add_textbox(cls._pct_x(6.0), cls._pct_y(38.0), cls._pct_w(48.0), cls._pct_h(46.0))
        tf_bullets = tb_bullets.text_frame
        tf_bullets.word_wrap = True

        for i, b in enumerate(bullets):
            p = tf_bullets.paragraphs[0] if i == 0 else tf_bullets.add_paragraph()
            p.text = f"•  {b}"
            p.font.size = Pt(14)
            p.font.color.rgb = palette["text"]
            p.space_after = Pt(12)

        # Right Column: Highlight Card Shape
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            cls._pct_x(58.0), cls._pct_y(38.0),
            cls._pct_w(36.0), cls._pct_h(46.0)
        )
        card.fill.solid()
        card.fill.fore_color.rgb = palette["card_bg"]
        card.line.color.rgb = palette["accent"]
        card.line.width = Pt(1.5)

        tb_card = slide.shapes.add_textbox(cls._pct_x(60.0), cls._pct_y(41.0), cls._pct_w(32.0), cls._pct_h(40.0))
        tf_card = tb_card.text_frame
        tf_card.word_wrap = True

        p_ht = tf_card.paragraphs[0]
        p_ht.text = highlight_title
        p_ht.font.size = Pt(16)
        p_ht.font.bold = True
        p_ht.font.color.rgb = palette["accent"]
        p_ht.space_after = Pt(10)

        p_hb = tf_card.add_paragraph()
        p_hb.text = highlight_body
        p_hb.font.size = Pt(13)
        p_hb.font.color.rgb = palette["text"]

    @classmethod
    def _build_metrics_slide(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor]) -> None:
        metrics = slide_dict.get("metrics") or [
            {"value": "94%", "label": "Source Grounding", "note": "Verified sources"},
            {"value": "30d", "label": "Freshness Window", "note": "Target recency"},
            {"value": "100%", "label": "Separation", "note": "Fact from analysis"},
            {"value": "4.8x", "label": "Efficiency", "note": "Meeting readiness"},
        ]
        count = min(4, len(metrics))
        w_pct = 20.0
        gap_pct = 2.5
        start_x = 6.0

        for i, m in enumerate(metrics[:count]):
            x_pct = start_x + i * (w_pct + gap_pct)

            # Metric Box
            box = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                cls._pct_x(x_pct), cls._pct_y(38.0),
                cls._pct_w(w_pct), cls._pct_h(46.0)
            )
            box.fill.solid()
            box.fill.fore_color.rgb = palette["card_bg"]
            box.line.color.rgb = palette["card_border"]
            box.line.width = Pt(1)

            tb = slide.shapes.add_textbox(
                cls._pct_x(x_pct + 1.0), cls._pct_y(41.0),
                cls._pct_w(w_pct - 2.0), cls._pct_h(40.0)
            )
            tf = tb.text_frame
            tf.word_wrap = True

            p_val = tf.paragraphs[0]
            p_val.text = str(m.get("value") or m.get("num") or "—")
            p_val.font.size = Pt(32)
            p_val.font.bold = True
            p_val.font.color.rgb = palette["accent"]
            p_val.space_after = Pt(8)

            p_lbl = tf.add_paragraph()
            p_lbl.text = str(m.get("label") or m.get("title") or "Metric")
            p_lbl.font.size = Pt(13)
            p_lbl.font.bold = True
            p_lbl.font.color.rgb = palette["text"]
            p_lbl.space_after = Pt(4)

            p_note = tf.add_paragraph()
            p_note.text = str(m.get("note") or m.get("desc") or "")
            p_note.font.size = Pt(11)
            p_note.font.color.rgb = palette["muted"]

    @classmethod
    def _build_timeline_slide(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor]) -> None:
        events = slide_dict.get("events") or [
            {"date": "Q1 2026", "title": "Platform Scaling", "desc": "Expanded enterprise client adoption."},
            {"date": "Q2 2026", "title": "Strategic Alliances", "desc": "Integrated ecosystem partnership network."},
            {"date": "Current", "title": "Executive Momentum", "desc": "Active commercial discussions underway."}
        ]
        count = min(3, len(events))
        w_pct = 26.5
        gap_pct = 4.0
        start_x = 6.0

        for i, ev in enumerate(events[:count]):
            x_pct = start_x + i * (w_pct + gap_pct)

            box = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                cls._pct_x(x_pct), cls._pct_y(38.0),
                cls._pct_w(w_pct), cls._pct_h(46.0)
            )
            box.fill.solid()
            box.fill.fore_color.rgb = palette["card_bg"]
            box.line.color.rgb = palette["card_border"]

            tb = slide.shapes.add_textbox(
                cls._pct_x(x_pct + 1.5), cls._pct_y(40.0),
                cls._pct_w(w_pct - 3.0), cls._pct_h(42.0)
            )
            tf = tb.text_frame
            tf.word_wrap = True

            p_date = tf.paragraphs[0]
            p_date.text = ev.get("date") or "Recent"
            p_date.font.size = Pt(11)
            p_date.font.bold = True
            p_date.font.color.rgb = palette["accent"]
            p_date.space_after = Pt(8)

            p_t = tf.add_paragraph()
            p_t.text = ev.get("title") or "Key Milestone"
            p_t.font.size = Pt(15)
            p_t.font.bold = True
            p_t.font.color.rgb = palette["text"]
            p_t.space_after = Pt(6)

            p_d = tf.add_paragraph()
            p_d.text = ev.get("desc") or ""
            p_d.font.size = Pt(11)
            p_d.font.color.rgb = palette["muted"]

    @classmethod
    def _build_leadership_slide(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor]) -> None:
        people = slide_dict.get("people") or [
            {"name": "Executive Counterpart", "role": "Chief Executive Officer", "note": "Primary decision maker."},
            {"name": "Commercial Lead", "role": "VP Strategic Partnerships", "note": "Key discussion stakeholder."},
            {"name": "Technical Sponsor", "role": "Head of Enterprise Systems", "note": "Architectural alignment."},
        ]
        count = min(3, len(people))
        w_pct = 26.5
        gap_pct = 4.0
        start_x = 6.0

        for i, person in enumerate(people[:count]):
            x_pct = start_x + i * (w_pct + gap_pct)

            box = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                cls._pct_x(x_pct), cls._pct_y(38.0),
                cls._pct_w(w_pct), cls._pct_h(46.0)
            )
            box.fill.solid()
            box.fill.fore_color.rgb = palette["card_bg"]
            box.line.color.rgb = palette["card_border"]

            tb = slide.shapes.add_textbox(
                cls._pct_x(x_pct + 1.5), cls._pct_y(40.0),
                cls._pct_w(w_pct - 3.0), cls._pct_h(42.0)
            )
            tf = tb.text_frame
            tf.word_wrap = True

            p_name = tf.paragraphs[0]
            p_name.text = person.get("name") or "Executive"
            p_name.font.size = Pt(16)
            p_name.font.bold = True
            p_name.font.color.rgb = palette["text"]
            p_name.space_after = Pt(4)

            p_role = tf.add_paragraph()
            p_role.text = person.get("role") or "Leadership"
            p_role.font.size = Pt(12)
            p_role.font.bold = True
            p_role.font.color.rgb = palette["accent"]
            p_role.space_after = Pt(8)

            p_note = tf.add_paragraph()
            p_note.text = person.get("note") or person.get("bio") or ""
            p_note.font.size = Pt(11)
            p_note.font.color.rgb = palette["muted"]

    @classmethod
    def _build_conclusion_slide(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor]) -> None:
        actions = slide_dict.get("actionItems") or [
            "Confirm alignment on core strategic deliverables and timeline.",
            "Establish joint working committee and communication rhythm.",
            "Schedule post-meeting technical and commercial follow-up.",
            "Review mutual non-disclosure and partnership documentation."
        ]
        takeaway = slide_dict.get("takeaway") or "Be ready for what matters: lead every conversation with verified clarity."

        # Left Checklist
        tb_chk = slide.shapes.add_textbox(cls._pct_x(6.0), cls._pct_y(38.0), cls._pct_w(48.0), cls._pct_h(46.0))
        tf_chk = tb_chk.text_frame
        tf_chk.word_wrap = True

        for i, item in enumerate(actions):
            p = tf_chk.paragraphs[0] if i == 0 else tf_chk.add_paragraph()
            p.text = f"✓  {item}"
            p.font.size = Pt(13)
            p.font.color.rgb = palette["text"]
            p.space_after = Pt(10)

        # Right Takeaway Banner
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            cls._pct_x(58.0), cls._pct_y(38.0),
            cls._pct_w(36.0), cls._pct_h(46.0)
        )
        card.fill.solid()
        card.fill.fore_color.rgb = palette["card_bg"]
        card.line.color.rgb = palette["accent"]
        card.line.width = Pt(1.5)

        tb_card = slide.shapes.add_textbox(cls._pct_x(60.0), cls._pct_y(41.0), cls._pct_w(32.0), cls._pct_h(40.0))
        tf_card = tb_card.text_frame
        tf_card.word_wrap = True

        p_t = tf_card.paragraphs[0]
        p_t.text = "Strategic Alignment Goal"
        p_t.font.size = Pt(16)
        p_t.font.bold = True
        p_t.font.color.rgb = palette["accent"]
        p_t.space_after = Pt(10)

        p_b = tf_card.add_paragraph()
        p_b.text = takeaway
        p_b.font.size = Pt(13)
        p_b.font.color.rgb = palette["text"]

    @classmethod
    def _build_comparison_slide(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor]) -> None:
        # Left Box (Traditional)
        left_box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            cls._pct_x(6.0), cls._pct_y(38.0),
            cls._pct_w(42.0), cls._pct_h(46.0)
        )
        left_box.fill.solid()
        left_box.fill.fore_color.rgb = palette["card_bg"]
        left_box.line.color.rgb = palette["card_border"]

        tb_l = slide.shapes.add_textbox(cls._pct_x(8.0), cls._pct_y(40.0), cls._pct_w(38.0), cls._pct_h(42.0))
        tf_l = tb_l.text_frame
        tf_l.word_wrap = True

        p_lt = tf_l.paragraphs[0]
        p_lt.text = "Traditional Diligence"
        p_lt.font.size = Pt(16)
        p_lt.font.bold = True
        p_lt.font.color.rgb = palette["muted"]
        p_lt.space_after = Pt(10)

        items_l = [
            "Unverified web speculation and stale news",
            "Slow manual diligence across disconnected sources",
            "High risk of hallucinated or out-of-date claims"
        ]
        for it in items_l:
            p = tf_l.add_paragraph()
            p.text = f"✕  {it}"
            p.font.size = Pt(12)
            p.font.color.rgb = palette["muted"]
            p.space_after = Pt(8)

        # Right Box (VelQora Grounded Moat)
        right_box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            cls._pct_x(52.0), cls._pct_y(38.0),
            cls._pct_w(42.0), cls._pct_h(46.0)
        )
        right_box.fill.solid()
        right_box.fill.fore_color.rgb = palette["card_bg"]
        right_box.line.color.rgb = palette["accent"]
        right_box.line.width = Pt(1.5)

        tb_r = slide.shapes.add_textbox(cls._pct_x(54.0), cls._pct_y(40.0), cls._pct_w(38.0), cls._pct_h(42.0))
        tf_r = tb_r.text_frame
        tf_r.word_wrap = True

        p_rt = tf_r.paragraphs[0]
        p_rt.text = "VelQora Verified Moat"
        p_rt.font.size = Pt(16)
        p_rt.font.bold = True
        p_rt.font.color.rgb = palette["accent"]
        p_rt.space_after = Pt(10)

        items_r = [
            "Deterministic claim-by-claim grounding matrix",
            "30-day bounded freshness window for verified news",
            "Actionable executive alignment and presentation deck"
        ]
        for it in items_r:
            p = tf_r.add_paragraph()
            p.text = f"✓  {it}"
            p.font.size = Pt(12)
            p.font.color.rgb = palette["text"]
            p.space_after = Pt(8)

    @classmethod
    def _build_chart_slide(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor]) -> None:
        # Genuine python-pptx clustered column chart on the left
        chart_data = CategoryChartData()
        chart_data.categories = ["Grounding", "Freshness", "Fact-Checking"]
        chart_data.add_series("Verified %", (94, 100, 88))

        chart_shape = slide.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            cls._pct_x(6.0), cls._pct_y(38.0),
            cls._pct_w(50.0), cls._pct_h(46.0),
            chart_data
        )
        chart = chart_shape.chart
        chart.has_legend = False

        # Right Summary Box
        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            cls._pct_x(60.0), cls._pct_y(38.0),
            cls._pct_w(34.0), cls._pct_h(46.0)
        )
        box.fill.solid()
        box.fill.fore_color.rgb = palette["card_bg"]
        box.line.color.rgb = palette["accent"]
        box.line.width = Pt(1.5)

        tb = slide.shapes.add_textbox(cls._pct_x(62.0), cls._pct_y(42.0), cls._pct_w(30.0), cls._pct_h(38.0))
        tf = tb.text_frame
        tf.word_wrap = True

        p_num = tf.paragraphs[0]
        p_num.text = "94%"
        p_num.font.size = Pt(40)
        p_num.font.bold = True
        p_num.font.color.rgb = palette["accent"]
        p_num.space_after = Pt(6)

        p_title = tf.add_paragraph()
        p_title.text = "Deterministic Ground Truth"
        p_title.font.size = Pt(14)
        p_title.font.bold = True
        p_title.font.color.rgb = palette["text"]
        p_title.space_after = Pt(6)

        p_desc = tf.add_paragraph()
        p_desc.text = "Structured data visualization with cross-referenced verified research sources."
        p_desc.font.size = Pt(11)
        p_desc.font.color.rgb = palette["muted"]

    @classmethod
    def _add_custom_elements(cls, slide, custom_elements: List[Dict[str, Any]], palette: Dict[str, RGBColor]) -> None:
        for el in custom_elements:
            x = float(el.get("x", 10.0))
            y = float(el.get("y", 40.0))
            w = float(el.get("w", 30.0))
            h = float(el.get("h", 15.0))
            content = str(el.get("content") or "")
            el_type = el.get("type", "text")

            if el_type == "shape":
                shape = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    cls._pct_x(x), cls._pct_y(y), cls._pct_w(w), cls._pct_h(h)
                )
                shape.fill.solid()
                shape.fill.fore_color.rgb = palette["card_bg"]
                shape.line.color.rgb = palette["accent"]
                shape.line.width = Pt(1)
                if content:
                    tf = shape.text_frame
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = content
                    p.font.size = Pt(12)
                    p.font.color.rgb = palette["text"]
            elif el_type == "divider":
                div = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE,
                    cls._pct_x(x), cls._pct_y(y), cls._pct_w(w), cls._pct_h(0.5)
                )
                div.fill.solid()
                div.fill.fore_color.rgb = palette["accent"]
                div.line.fill.background()
            else:
                tb = slide.shapes.add_textbox(cls._pct_x(x), cls._pct_y(y), cls._pct_w(w), cls._pct_h(h))
                tf = tb.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = content
                p.font.size = Pt(13)
                p.font.color.rgb = palette["text"]

    @classmethod
    def _add_slide_footer(cls, slide, slide_dict: Dict[str, Any], palette: Dict[str, RGBColor], deck_title: str) -> None:
        footer_text = slide_dict.get("footer") or f"{deck_title} • VelQora Intelligence"

        # Footer Left
        tb_l = slide.shapes.add_textbox(cls._pct_x(6.0), cls._pct_y(92.0), cls._pct_w(70.0), cls._pct_h(4.0))
        tf_l = tb_l.text_frame
        tf_l.word_wrap = True
        tf_l.margin_left = tf_l.margin_top = tf_l.margin_right = tf_l.margin_bottom = 0
        p_l = tf_l.paragraphs[0]
        p_l.text = footer_text
        p_l.font.size = Pt(9)
        p_l.font.color.rgb = palette["muted"]

        # Footer Right (Branding)
        tb_r = slide.shapes.add_textbox(cls._pct_x(78.0), cls._pct_y(92.0), cls._pct_w(16.0), cls._pct_h(4.0))
        tf_r = tb_r.text_frame
        tf_r.word_wrap = True
        tf_r.margin_left = tf_r.margin_top = tf_r.margin_right = tf_r.margin_bottom = 0
        p_r = tf_r.paragraphs[0]
        p_r.text = "VelQora AI"
        p_r.font.size = Pt(9)
        p_r.font.bold = True
        p_r.font.color.rgb = palette["accent"]
        p_r.alignment = PP_ALIGN.RIGHT

    @classmethod
    def _add_speaker_notes(cls, slide, slide_dict: Dict[str, Any]) -> None:
        notes_lines: List[str] = []
        if slide_dict.get("speaker_notes"):
            notes_lines.append(f"Speaker Notes:\n{slide_dict['speaker_notes']}")
        if slide_dict.get("takeaway"):
            notes_lines.append(f"Key Takeaway:\n{slide_dict['takeaway']}")
        if slide_dict.get("source_references"):
            refs = "\n- ".join(slide_dict["source_references"])
            notes_lines.append(f"Verified Source References:\n- {refs}")

        if notes_lines:
            notes_slide = slide.notes_slide
            tf = notes_slide.notes_text_frame
            tf.text = "\n\n".join(notes_lines)
