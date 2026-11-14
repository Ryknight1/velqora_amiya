/* ============================================================
   VelQora Presentation Studio — Single Presentation State Manager
   Single source of truth for slides, configuration, theme, undo/redo,
   and persistent storage.
   ============================================================ */

class PresentationState {
  static THEMES = [
    {
      id: "corporate_blue",
      alias: "navy",
      name: "Corporate Blue",
      description: "Deep royal blue and midnight navy. High-authority boardroom aesthetic.",
      bg: "#0B1E3F",
      accent: "#FF5858",
      primary: "#1E40AF",
      secondary: "#3B82F6",
      text: "#FFFFFF"
    },
    {
      id: "minimal_white",
      alias: "light",
      name: "Minimal White",
      description: "Crisp studio white with slate typography and clean royal blue accents.",
      bg: "#FFFFFF",
      accent: "#2563EB",
      primary: "#0F172A",
      secondary: "#475569",
      text: "#0F172A"
    },
    {
      id: "dark_executive",
      alias: "coral",
      name: "Dark Executive",
      description: "Obsidian dark background with vivid coral accents and executive precision.",
      bg: "#10141D",
      accent: "#FF5858",
      primary: "#1E293B",
      secondary: "#334155",
      text: "#F8FAFC"
    },
    {
      id: "modern_gradient",
      alias: "gradient",
      name: "Modern Gradient",
      description: "Vibrant indigo and violet twilight gradient with high-impact magenta highlights.",
      bg: "#1E1B4B",
      accent: "#EC4899",
      primary: "#6366F1",
      secondary: "#8B5CF6",
      text: "#FFFFFF"
    },
    {
      id: "clean_business",
      alias: "editorial",
      name: "Clean Business",
      description: "Sophisticated corporate slate with crisp teal and neutral gray structuring.",
      bg: "#F1F5F9",
      accent: "#0D9488",
      primary: "#1E293B",
      secondary: "#0284C7",
      text: "#0F172A"
    },
    {
      id: "tech_innovation",
      alias: "slate",
      name: "Technology and Innovation",
      description: "High-contrast cyber slate with electric cyan and emerald tech highlights.",
      bg: "#030712",
      accent: "#06B6D4",
      primary: "#0B132B",
      secondary: "#10B981",
      text: "#F0FDFA"
    }
  ];

  static LAYOUTS = [
    { id: "title", name: "Title Slide", icon: "📑", desc: "Hero introduction with kicker, title, and presenter meta" },
    { id: "cards", name: "Key Themes & Cards", icon: "🗂️", desc: "Three structured insight cards with source badges" },
    { id: "split", name: "Two-Column Split", icon: "⚖️", desc: "Narrative takeaway bullets with supporting evidence block" },
    { id: "metrics", name: "Metrics & Stats", icon: "📊", desc: "Four bold quantitative KPI blocks with contextual notes" },
    { id: "timeline", name: "Recent Developments", icon: "⏱️", desc: "Chronological milestone timeline of verified events" },
    { id: "leadership", name: "Leadership & Team", icon: "👥", desc: "Key executive profiles, decision makers, and roles" },
    { id: "conclusion", name: "Action Plan & Next Steps", icon: "🎯", desc: "Meeting checklist, recommended strategy, and takeaway" },
    { id: "comparison", name: "Comparison Matrix", icon: "🆚", desc: "Side-by-side strategic comparison of capabilities and value" },
    { id: "chart_focused", name: "Charts & Visuals", icon: "📈", desc: "Structured data visualization with bar metrics and donut grounding ring" }
  ];

  constructor(initialData = null) {
    this.listeners = {
      change: [],
      slideChange: [],
      selectionChange: [],
      historyChange: []
    };

    this.undoStack = [];
    this.redoStack = [];
    this.maxHistory = 30;
    this.isDirty = false;
    this.lastSavedAt = null;

    if (initialData) {
      this.deck = this._sanitizeDeck(initialData);
    } else {
      this.deck = this._createDefaultDeck();
    }
  }

  /* ---------------- Event System ---------------- */
  on(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event].push(callback);
    }
    return () => {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    };
  }

  _emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(cb => {
        try { cb(data, this); } catch (err) { console.error(`Error in ${event} listener:`, err); }
      });
    }
  }

  /* ---------------- History (Undo / Redo) ---------------- */
  _pushSnapshot() {
    const snapshot = JSON.stringify({
      title: this.deck.title,
      theme: this.deck.theme,
      config: this.deck.config,
      slides: this.deck.slides,
      activeSlideIndex: this.deck.activeSlideIndex
    });

    this.undoStack.push(snapshot);
    if (this.undoStack.length > this.maxHistory) {
      this.undoStack.shift();
    }
    this.redoStack = [];
    this.isDirty = true;
    this._emit("historyChange", { canUndo: this.canUndo(), canRedo: this.canRedo() });
  }

  canUndo() {
    return this.undoStack.length > 0;
  }

  canRedo() {
    return this.redoStack.length > 0;
  }

  undo() {
    if (!this.canUndo()) return false;
    const current = JSON.stringify({
      title: this.deck.title,
      theme: this.deck.theme,
      config: this.deck.config,
      slides: this.deck.slides,
      activeSlideIndex: this.deck.activeSlideIndex
    });
    this.redoStack.push(current);

    const prev = JSON.parse(this.undoStack.pop());
    this.deck.title = prev.title;
    this.deck.theme = prev.theme;
    this.deck.config = prev.config;
    this.deck.slides = prev.slides;
    this.deck.activeSlideIndex = Math.min(prev.activeSlideIndex, this.deck.slides.length - 1);
    this.deck.selectedElement = null;

    this.isDirty = true;
    this._emit("change", { source: "undo" });
    this._emit("slideChange", { activeIndex: this.deck.activeSlideIndex });
    this._emit("historyChange", { canUndo: this.canUndo(), canRedo: this.canRedo() });
    return true;
  }

  redo() {
    if (!this.canRedo()) return false;
    const current = JSON.stringify({
      title: this.deck.title,
      theme: this.deck.theme,
      config: this.deck.config,
      slides: this.deck.slides,
      activeSlideIndex: this.deck.activeSlideIndex
    });
    this.undoStack.push(current);

    const next = JSON.parse(this.redoStack.pop());
    this.deck.title = next.title;
    this.deck.theme = next.theme;
    this.deck.config = next.config;
    this.deck.slides = next.slides;
    this.deck.activeSlideIndex = Math.min(next.activeSlideIndex, this.deck.slides.length - 1);
    this.deck.selectedElement = null;

    this.isDirty = true;
    this._emit("change", { source: "redo" });
    this._emit("slideChange", { activeIndex: this.deck.activeSlideIndex });
    this._emit("historyChange", { canUndo: this.canUndo(), canRedo: this.canRedo() });
    return true;
  }

  /* ---------------- Getters ---------------- */
  getDeck() {
    return this.deck;
  }

  getTitle() {
    return this.deck.title || "Meeting Presentation";
  }

  getTheme() {
    return this.deck.theme || "navy";
  }

  getConfig() {
    return this.deck.config;
  }

  getSlides() {
    return this.deck.slides;
  }

  getSlideCount() {
    return this.deck.slides.length;
  }

  getActiveSlideIndex() {
    return this.deck.activeSlideIndex;
  }

  getActiveSlide() {
    return this.deck.slides[this.deck.activeSlideIndex] || this.deck.slides[0] || null;
  }

  getSelectedElement() {
    return this.deck.selectedElement;
  }

  /* ---------------- Mutators ---------------- */
  setTitle(title) {
    if (!title || title === this.deck.title) return;
    this._pushSnapshot();
    this.deck.title = title.trim();
    this._emit("change", { source: "title" });
  }

  setTheme(themeId) {
    const found = PresentationState.THEMES.find(t => t.id === themeId || t.alias === themeId);
    const resolvedId = found ? found.id : "corporate_blue";
    if (this.deck.theme === resolvedId) return;
    this._pushSnapshot();
    this.deck.theme = resolvedId;
    if (this.deck.config) this.deck.config.theme = resolvedId;
    this._emit("change", { source: "theme", theme: resolvedId });
  }

  changeSlideTitle(index, newTitle) {
    const idx = index >= 0 ? index : this.deck.activeSlideIndex;
    if (idx < 0 || idx >= this.deck.slides.length || !newTitle) return;
    this._pushSnapshot();
    this.deck.slides[idx].title = newTitle.trim();
    this._emit("change", { source: "changeSlideTitle", index: idx, title: newTitle });
  }

  updateElementStyle(slideIndex, elementKey, stylePatch) {
    const idx = slideIndex >= 0 ? slideIndex : this.deck.activeSlideIndex;
    if (idx < 0 || idx >= this.deck.slides.length || !stylePatch) return;
    const slide = this.deck.slides[idx];
    if (!slide.elementStyles) slide.elementStyles = {};
    if (!slide.elementStyles[elementKey]) slide.elementStyles[elementKey] = {};
    this._pushSnapshot();
    Object.assign(slide.elementStyles[elementKey], stylePatch);
    this._emit("change", { source: "updateElementStyle", slideIndex: idx, elementKey });
  }

  updateElementPosition(slideIndex, elementKey, posPatch) {
    const idx = slideIndex >= 0 ? slideIndex : this.deck.activeSlideIndex;
    if (idx < 0 || idx >= this.deck.slides.length || !posPatch) return;
    const slide = this.deck.slides[idx];
    if (!slide.elementPositions) slide.elementPositions = {};
    if (!slide.elementPositions[elementKey]) slide.elementPositions[elementKey] = { x: 5, y: 20, w: 90, h: 20 };
    this._pushSnapshot();
    Object.assign(slide.elementPositions[elementKey], posPatch);
    this._emit("change", { source: "updateElementPosition", slideIndex: idx, elementKey });
  }

  addElement(slideIndex, elementData) {
    const idx = slideIndex >= 0 ? slideIndex : this.deck.activeSlideIndex;
    if (idx < 0 || idx >= this.deck.slides.length || !elementData) return;
    this._pushSnapshot();
    const slide = this.deck.slides[idx];
    if (!Array.isArray(slide.customElements)) slide.customElements = [];
    const el = Object.assign({
      id: "custom_" + Math.random().toString(36).substr(2, 7),
      type: "text",
      content: "New Text Block",
      x: 10,
      y: 40,
      w: 40,
      h: 20,
      fontSize: "14px",
      fontWeight: "400",
      color: "var(--slide-text)",
      bg: "transparent"
    }, elementData);
    slide.customElements.push(el);
    this.deck.selectedElement = el.id;
    this._emit("change", { source: "addElement", slideIndex: idx });
    return el.id;
  }

  deleteElement(slideIndex, elementKey) {
    const idx = slideIndex >= 0 ? slideIndex : this.deck.activeSlideIndex;
    if (idx < 0 || idx >= this.deck.slides.length || !elementKey) return;
    const slide = this.deck.slides[idx];
    this._pushSnapshot();

    if (Array.isArray(slide.customElements)) {
      const initLen = slide.customElements.length;
      slide.customElements = slide.customElements.filter(e => e.id !== elementKey);
      if (slide.customElements.length !== initLen) {
        this.deck.selectedElement = null;
        this._emit("change", { source: "deleteElement", slideIndex: idx });
        return true;
      }
    }

    if (elementKey.startsWith("card_")) {
      const cIdx = parseInt(elementKey.split("_")[1], 10);
      if (Array.isArray(slide.cards) && slide.cards[cIdx]) {
        slide.cards.splice(cIdx, 1);
        this.deck.selectedElement = null;
        this._emit("change", { source: "deleteCard", slideIndex: idx });
        return true;
      }
    } else if (elementKey.startsWith("bullet_")) {
      const bIdx = parseInt(elementKey.split("_")[1], 10);
      if (Array.isArray(slide.bullets) && slide.bullets[bIdx] !== undefined) {
        slide.bullets.splice(bIdx, 1);
        this.deck.selectedElement = null;
        this._emit("change", { source: "deleteBullet", slideIndex: idx });
        return true;
      }
    }

    this.deck.selectedElement = null;
    this._emit("change", { source: "deleteElement", slideIndex: idx });
    return true;
  }

  setActiveSlide(index) {
    if (index < 0 || index >= this.deck.slides.length || index === this.deck.activeSlideIndex) return;
    this.deck.activeSlideIndex = index;
    this.deck.selectedElement = null;
    this._emit("slideChange", { activeIndex: index });
    this._emit("selectionChange", { element: null });
  }

  selectElement(elementId) {
    this.deck.selectedElement = elementId;
    this._emit("selectionChange", { element: elementId });
  }

  addSlide(layout = "cards", customData = null, insertAt = -1) {
    this._pushSnapshot();
    const newSlide = customData ? Object.assign(this._createSlideByLayout(layout), customData) : this._createSlideByLayout(layout);
    newSlide.id = "slide_" + Math.random().toString(36).substr(2, 9);

    if (insertAt < 0 || insertAt >= this.deck.slides.length) {
      this.deck.slides.push(newSlide);
      this.deck.activeSlideIndex = this.deck.slides.length - 1;
    } else {
      this.deck.slides.splice(insertAt + 1, 0, newSlide);
      this.deck.activeSlideIndex = insertAt + 1;
    }

    this.deck.selectedElement = null;
    this._emit("change", { source: "addSlide" });
    this._emit("slideChange", { activeIndex: this.deck.activeSlideIndex });
    return this.deck.activeSlideIndex;
  }

  duplicateSlide(index = -1) {
    const idx = index >= 0 ? index : this.deck.activeSlideIndex;
    if (idx < 0 || idx >= this.deck.slides.length) return false;

    this._pushSnapshot();
    const original = this.deck.slides[idx];
    const clone = JSON.parse(JSON.stringify(original));
    clone.id = "slide_" + Math.random().toString(36).substr(2, 9);
    clone.title = (clone.title || "Slide") + " (Copy)";

    this.deck.slides.splice(idx + 1, 0, clone);
    this.deck.activeSlideIndex = idx + 1;
    this.deck.selectedElement = null;

    this._emit("change", { source: "duplicateSlide" });
    this._emit("slideChange", { activeIndex: this.deck.activeSlideIndex });
    return true;
  }

  deleteSlide(index = -1) {
    if (this.deck.slides.length <= 1) return false; // Always keep at least 1 slide
    const idx = index >= 0 ? index : this.deck.activeSlideIndex;
    if (idx < 0 || idx >= this.deck.slides.length) return false;

    this._pushSnapshot();
    this.deck.slides.splice(idx, 1);
    if (this.deck.activeSlideIndex >= this.deck.slides.length) {
      this.deck.activeSlideIndex = this.deck.slides.length - 1;
    }
    this.deck.selectedElement = null;

    this._emit("change", { source: "deleteSlide" });
    this._emit("slideChange", { activeIndex: this.deck.activeSlideIndex });
    return true;
  }

  moveSlide(fromIndex, toIndex) {
    if (fromIndex === toIndex || fromIndex < 0 || fromIndex >= this.deck.slides.length || toIndex < 0 || toIndex >= this.deck.slides.length) {
      return false;
    }

    this._pushSnapshot();
    const [moved] = this.deck.slides.splice(fromIndex, 1);
    this.deck.slides.splice(toIndex, 0, moved);
    this.deck.activeSlideIndex = toIndex;

    this._emit("change", { source: "moveSlide" });
    this._emit("slideChange", { activeIndex: toIndex });
    return true;
  }

  updateSlide(index, patch) {
    const idx = index >= 0 ? index : this.deck.activeSlideIndex;
    if (idx < 0 || idx >= this.deck.slides.length || !patch) return;

    this._pushSnapshot();
    Object.assign(this.deck.slides[idx], patch);
    this._emit("change", { source: "updateSlide", index: idx });
  }

  updateSlideElement(slideIndex, elementKey, value, isDirectEdit = false) {
    const idx = slideIndex >= 0 ? slideIndex : this.deck.activeSlideIndex;
    if (idx < 0 || idx >= this.deck.slides.length) return;

    const slide = this.deck.slides[idx];
    if (isDirectEdit) {
      // Debounced or direct inline edit without full snapshot for smooth typing
      slide[elementKey] = value;
      this.isDirty = true;
      this._emit("change", { source: "inlineEdit", slideIndex: idx, elementKey });
    } else {
      this._pushSnapshot();
      slide[elementKey] = value;
      this._emit("change", { source: "updateElement", slideIndex: idx, elementKey });
    }
  }

  updateConfig(newConfig, rebuild = false, briefingData = null) {
    this._pushSnapshot();
    this.deck.config = Object.assign({}, this.deck.config, newConfig || {});

    if (newConfig && newConfig.title) {
      this.deck.title = newConfig.title;
    }
    if (newConfig && newConfig.theme) {
      this.deck.theme = newConfig.theme;
    }

    if (rebuild) {
      this.deck.slides = this._buildSlidesFromConfig(this.deck.config, briefingData);
      this.deck.activeSlideIndex = 0;
    }

    this._emit("change", { source: "config" });
    if (rebuild) {
      this._emit("slideChange", { activeIndex: 0 });
    }
  }

  /* ---------------- Presentation Builders & Seeders ---------------- */
  _createDefaultDeck(entityName = "Acme Corp", meetingPurpose = "Strategic Partnership") {
    return {
      id: "pres_" + Math.random().toString(36).substr(2, 9),
      title: `${entityName} — Strategic Briefing`,
      theme: "navy",
      config: {
        title: `${entityName} — Strategic Briefing`,
        slideCount: 7,
        audience: "Executive Leadership",
        purpose: meetingPurpose,
        tone: "professional",
        theme: "navy",
        detailLevel: "balanced",
        topicsInclude: ["overview", "leadership", "developments", "strategy", "questions", "risks", "next_steps"],
        topicsExclude: ["speculation"]
      },
      activeSlideIndex: 0,
      selectedElement: null,
      slides: this._buildDefault7Slides(entityName, meetingPurpose)
    };
  }

  _createSlideByLayout(layout) {
    switch (layout) {
      case "title":
        return {
          layout: "title",
          kicker: "Executive Briefing",
          title: "Strategic Overview & Meeting Briefing",
          subtitle: "Executive alignment, verified market intelligence, and partnership strategy.",
          footer: "VelQora Intelligence • Confidential"
        };
      case "split":
        return {
          layout: "split",
          kicker: "Market Thesis",
          title: "Strategic Thesis & Competitive Position",
          subtitle: "Core alignment drivers and validated business differentiation.",
          bullets: [
            "Market-leading operational efficiency and unified platform capabilities.",
            "Demonstrated enterprise traction across high-value client segments.",
            "Strong verified moat with defensible technological advantage."
          ],
          highlightTitle: "Key Strategic Takeaway",
          highlightBody: "The company's expansion into global enterprise accounts provides an immediate commercial synergy window.",
          footer: "VelQora Intelligence • Source Verified"
        };
      case "metrics":
        return {
          layout: "metrics",
          kicker: "Key Metrics",
          title: "Quantitative Indicators & Verification Matrix",
          subtitle: "Verified ground truth metrics from multi-source cross-referencing.",
          metrics: [
            { num: "94%", label: "Source Grounding", note: "Verified against multi-source evidence" },
            { num: "30 Days", label: "Research Window", note: "Recent verified market developments" },
            { num: "4.8x", label: "Enterprise Velocity", note: "Reported growth in target segments" },
            { num: "100%", label: "Deterministic Check", note: "Zero hallucinations in factual citations" }
          ],
          footer: "VelQora Grounding Matrix"
        };
      case "timeline":
        return {
          layout: "timeline",
          kicker: "Market Velocity",
          title: "Recent Verified Developments",
          subtitle: "Chronological timeline of verified news, releases, and strategic announcements.",
          events: [
            { date: "Current Quarter", title: "Enterprise Platform Release", desc: "Launched major expansion featuring enhanced automation and unified compliance.", source: "Press Announcement" },
            { date: "Last Month", title: "Strategic Ecosystem Expansion", desc: "Secured key partner integrations expanding addressable market penetration.", source: "Marketwire" },
            { date: "Recent", title: "Executive Leadership Appointment", desc: "Strengthened commercial leadership to drive accelerated growth.", source: "Verified News" }
          ],
          footer: "Verified Source Timeline"
        };
      case "leadership":
        return {
          layout: "leadership",
          kicker: "Stakeholder Intelligence",
          title: "Key People & Decision Makers",
          subtitle: "Verified executive leadership and strategic discussion counterparts.",
          people: [
            { name: "Chief Executive Officer", role: "Co-Founder & Executive Lead", note: "Leads product vision, corporate strategy, and long-term capital allocation." },
            { name: "Chief Technology Officer", role: "Head of Engineering", note: "Directs technical architecture, core platform infrastructure, and AI systems." },
            { name: "VP of Strategic Partnerships", role: "Commercial Operations", note: "Primary counterpart for partnership evaluation, deal structure, and rollout." }
          ],
          footer: "Stakeholder Matrix"
        };
      case "conclusion":
        return {
          layout: "conclusion",
          kicker: "Meeting Strategy",
          title: "Strategic Takeaways & Recommended Action Plan",
          subtitle: "Actionable roadmap and priorities for immediate meeting execution.",
          actionItems: [
            "Confirm alignment on core strategic objectives and target implementation milestones.",
            "Address key operational risks early to build shared trust and clarity.",
            "Propose concrete next steps with designated stakeholder ownership."
          ],
          takeaway: "Enter the conversation prepared with verified facts to anchor high-value strategic momentum.",
          footer: "VelQora Action Plan"
        };
      case "cards":
      default:
        return {
          layout: "cards",
          kicker: "Core Insights",
          title: "Strategic Pillars & Market Value Drivers",
          subtitle: "Three foundational pillars powering sustainable growth and defensibility.",
          cards: [
            { tag: "Pillar 01", title: "Defensible Platform Advantage", desc: "Proprietary technology stack creating high switching costs and customer stickiness.", badge: "Verified Fact" },
            { tag: "Pillar 02", title: "Expanding Market Opportunity", desc: "Aggressive tailwinds accelerating enterprise demand across primary verticals.", badge: "Market Trend" },
            { tag: "Pillar 03", title: "Commercial Synergies", desc: "Clear bilateral value creation through shared capabilities and audience reach.", badge: "Strategic Fit" }
          ],
          footer: "VelQora Strategic Briefing"
        };
    }
  }

  _buildDefault7Slides(entityName, meetingPurpose) {
    return [
      {
        id: "slide_1",
        layout: "title",
        kicker: "Executive Briefing",
        title: `${entityName} — Strategic Briefing`,
        subtitle: `Comprehensive meeting preparation and intelligence analysis for ${meetingPurpose}.`,
        footer: `VelQora Intelligence • ${entityName}`
      },
      {
        id: "slide_2",
        layout: "cards",
        kicker: "Company Overview",
        title: "Executive Overview & Business Foundation",
        subtitle: `Core business focus, operating model, and market positioning of ${entityName}.`,
        cards: [
          { tag: "Mission", title: "Core Business Mission", desc: `Delivering mission-critical solutions in modern enterprise environments.`, badge: "Verified" },
          { tag: "Market", title: "Market Footprint", desc: "Active commercial engagement with top-tier international customers.", badge: "Verified" },
          { tag: "Pillars", title: "Operating Differentiation", desc: "High velocity execution combined with rigorous architectural reliability.", badge: "Insight" }
        ],
        footer: `${entityName} • Overview`
      },
      {
        id: "slide_3",
        layout: "timeline",
        kicker: "Market Velocity",
        title: "Recent Developments & Timeline",
        subtitle: "Key verified announcements and strategic milestones from the past 30 days.",
        events: [
          { date: "Recent", title: "Platform Expansion", desc: "Announced enhanced service capabilities to meet surging enterprise customer demand.", source: "Verified News" },
          { date: "Current Quarter", title: "Commercial Acceleration", desc: "Reported record quarter-over-quarter growth across strategic focus verticals.", source: "Marketwire" },
          { date: "Milestone", title: "Leadership & Hiring", desc: "Scaled executive and technical leadership teams to support continued growth.", source: "Press Release" }
        ],
        footer: `${entityName} • Recent News`
      },
      {
        id: "slide_4",
        layout: "leadership",
        kicker: "Stakeholder Intelligence",
        title: "Key Leadership & Decision Makers",
        subtitle: "Executive profiles and stakeholders driving strategic decisions.",
        people: [
          { name: "Executive Leadership", role: "Key Decision Maker", note: "Sets strategic priorities, capital allocation, and organizational vision." },
          { name: "Product & Engineering", role: "Technology Leadership", note: "Oversees core innovation, technical roadmap, and system scalability." },
          { name: "Commercial & Alliances", role: "Partnership Stakeholder", note: "Manages partner evaluation, commercial contracts, and joint go-to-market." }
        ],
        footer: `${entityName} • Key People`
      },
      {
        id: "slide_5",
        layout: "split",
        kicker: "Discussion Topics",
        title: "Strategic Talking Points",
        subtitle: "High-priority discussion angles to lead with confidence and precision.",
        bullets: [
          "Acknowledge recent momentum and explore mutual collaboration touchpoints.",
          "Identify how complementary capabilities address urgent industry bottlenecks.",
          "Establish measurable success criteria for short and medium term engagement."
        ],
        highlightTitle: "Meeting Purpose",
        highlightBody: `Ground discussion in mutual objectives: "${meetingPurpose}" with clear ROI validation.`,
        footer: "Discussion Framework"
      },
      {
        id: "slide_6",
        layout: "metrics",
        kicker: "Strategic Assessment",
        title: "Key Questions & Risk Factors",
        subtitle: "Proactive risk mitigation and strategic inquiries for deep alignment.",
        metrics: [
          { num: "01", label: "Strategic Priority", note: "What is their top business objective for this quarter?" },
          { num: "02", label: "Timeline & Budget", note: "What is the intended timeline and resource commitment?" },
          { num: "03", label: "Risk Mitigation", note: "What key compliance or integration risks must be addressed?" },
          { num: "04", label: "Decision Criteria", note: "Who are the final stakeholders required for sign-off?" }
        ],
        footer: "Risk & Alignment Matrix"
      },
      {
        id: "slide_7",
        layout: "conclusion",
        kicker: "Action Plan",
        title: "Meeting Strategy & Immediate Next Steps",
        subtitle: "Clear preparation checklist to maximize meeting impact.",
        actionItems: [
          "Open conversation by anchoring on verified recent developments.",
          "Address key questions early to establish credibility and transparency.",
          "Agree upon concrete follow-up deliverables and scheduled milestone review."
        ],
        takeaway: "Be ready for what matters: enter every conversation equipped with verified intelligence.",
        footer: "VelQora Presentation Studio"
      }
    ];
  }

  _buildSlidesFromConfig(config, briefingData) {
    const entityName = (briefingData && briefingData.entity && briefingData.entity.name) || config.title.split("—")[0].trim() || "Target Entity";
    const purpose = config.purpose || "Strategic Partnership";
    const count = parseInt(config.slideCount, 10) || 7;

    // Use briefing data if available
    const slides = [];

    // 1. Title Slide
    slides.push({
      id: "slide_1",
      layout: "title",
      kicker: config.audience ? `Prepared for: ${config.audience}` : "Executive Briefing",
      title: config.title || `${entityName} — Strategic Briefing`,
      subtitle: `Targeted presentation tailored for ${purpose} with verified research intelligence.`,
      footer: `VelQora Intelligence • ${config.tone || "Professional"} Tone`
    });

    // 2. Company Overview
    if (config.topicsInclude.includes("overview")) {
      const overviewText = briefingData && briefingData.overview ? briefingData.overview : `Operating overview and market positioning for ${entityName}.`;
      slides.push({
        id: "slide_" + (slides.length + 1),
        layout: "cards",
        kicker: "Executive Overview",
        title: `${entityName} — Foundation & Position`,
        subtitle: overviewText.slice(0, 140) + (overviewText.length > 140 ? "..." : ""),
        cards: [
          { tag: "Overview", title: "Business Foundation", desc: overviewText.slice(0, 160) || "Established enterprise presence.", badge: "Verified" },
          { tag: "Focus", title: "Core Capabilities", desc: "Delivering modern scalable technology and services.", badge: "Core Pillar" },
          { tag: "Strategy", title: "Strategic Positioning", desc: "Positioned for rapid expansion and enterprise partnership.", badge: "Strategic" }
        ],
        footer: `${entityName} • Overview`
      });
    }

    // 3. Recent Developments
    if (config.topicsInclude.includes("developments")) {
      const newsItems = (briefingData && briefingData.recent_developments && briefingData.recent_developments.length)
        ? briefingData.recent_developments.slice(0, 3)
        : (briefingData && briefingData.important_news && briefingData.important_news.length)
          ? briefingData.important_news.slice(0, 3)
          : null;

      const events = newsItems ? newsItems.map((n, i) => ({
        date: n.date || `Recent`,
        title: n.text ? n.text.slice(0, 60) + "..." : `Verified Update ${i + 1}`,
        desc: n.text || "Verified commercial development.",
        source: n.verification_status === "verified" ? "Verified Ground Truth" : "Reported News"
      })) : [
        { date: "Recent", title: "Commercial Momentum", desc: `Active market expansion and enterprise customer growth.`, source: "Verified News" },
        { date: "Current Quarter", title: "Service Innovation", desc: "Continuous improvements to core products and infrastructure.", source: "Marketwire" }
      ];

      slides.push({
        id: "slide_" + (slides.length + 1),
        layout: "timeline",
        kicker: "Market Velocity",
        title: "Recent Developments & Timeline",
        subtitle: `Verified announcements and developments within the active research window.`,
        events: events,
        footer: `${entityName} • Recent News`
      });
    }

    // 4. Leadership & People
    if (config.topicsInclude.includes("leadership")) {
      const peopleItems = (briefingData && briefingData.key_people && briefingData.key_people.length)
        ? briefingData.key_people.slice(0, 3)
        : null;

      const people = peopleItems ? peopleItems.map(p => ({
        name: p.name,
        role: p.role || "Executive Leadership",
        note: `Key decision maker identified in verified briefing data.`
      })) : [
        { name: "Executive Leadership", role: "Key Decision Maker", note: "Sets strategic priorities and capital direction." },
        { name: "Operations & Partnerships", role: "Strategic Stakeholder", note: "Evaluates bilateral commercial alignment." }
      ];

      slides.push({
        id: "slide_" + (slides.length + 1),
        layout: "leadership",
        kicker: "Stakeholder Intelligence",
        title: "Key People & Decision Makers",
        subtitle: `Key executive profiles relevant to ${purpose}.`,
        people: people,
        footer: `${entityName} • Leadership`
      });
    }

    // 5. Talking Points
    if (config.topicsInclude.includes("strategy")) {
      const points = (briefingData && briefingData.meeting_talking_points && briefingData.meeting_talking_points.length)
        ? briefingData.meeting_talking_points.slice(0, 3).map(p => p.text)
        : [
          `Anchor discussion on verified strengths and strategic momentum of ${entityName}.`,
          `Highlight concrete collaborative opportunities that produce mutual commercial lift.`,
          `Establish mutual success criteria and clear execution ownership.`
        ];

      slides.push({
        id: "slide_" + (slides.length + 1),
        layout: "split",
        kicker: "Meeting Framework",
        title: "Strategic Talking Points",
        subtitle: `Essential discussion points tailored for ${config.audience || "Executive Leadership"}.`,
        bullets: points,
        highlightTitle: "Primary Objective",
        highlightBody: purpose,
        footer: "Strategic Alignment"
      });
    }

    // 6. Metrics / Stats / Questions
    if (config.topicsInclude.includes("questions") || config.topicsInclude.includes("risks")) {
      const questions = (briefingData && briefingData.suggested_questions && briefingData.suggested_questions.length)
        ? briefingData.suggested_questions.slice(0, 4)
        : null;

      const metrics = questions ? questions.map((q, i) => ({
        num: `0${i + 1}`,
        label: "Strategic Question",
        note: q.text
      })) : [
        { num: "01", label: "Strategic Priority", note: `What is the top organizational focus for ${entityName} right now?` },
        { num: "02", label: "Timeline", note: "What timeline is envisioned for partnership milestones?" },
        { num: "03", label: "Key Risks", note: "What operational risks require mutual mitigation?" },
        { num: "04", label: "Next Steps", note: "What deliverables are needed for immediate greenlight?" }
      ];

      slides.push({
        id: "slide_" + (slides.length + 1),
        layout: "metrics",
        kicker: "Strategic Inquiry",
        title: "Key Questions & Risk Factors",
        subtitle: "Critical discussion questions grounded in current intelligence.",
        metrics: metrics,
        footer: "Inquiry Framework"
      });
    }

    // 7. Conclusion & Next Steps
    if (config.topicsInclude.includes("next_steps") || slides.length < count) {
      slides.push({
        id: "slide_" + (slides.length + 1),
        layout: "conclusion",
        kicker: "Next Steps",
        title: "Meeting Strategy & Action Plan",
        subtitle: `Clear roadmap to conclude the meeting with shared alignment and momentum.`,
        actionItems: [
          "Summarize agreed-upon discussion items and strategic alignment.",
          "Identify designated project leads for next stage evaluation.",
          "Schedule follow-up review meeting with concrete deliverable checkpoints."
        ],
        takeaway: `Be ready for what matters: turn research into strategic commercial success.`,
        footer: "VelQora Action Plan"
      });
    }

    // Adjust to exact slideCount requested
    while (slides.length > count && slides.length > 2) {
      slides.splice(slides.length - 2, 1);
    }
    while (slides.length < count) {
      slides.splice(slides.length - 1, 0, this._createSlideByLayout("cards"));
    }

    return slides;
  }

  /* ---------------- Storage & Persistence ---------------- */
  saveToStorage(storageKey = null) {
    const key = storageKey || (this.deck.id ? `vq_pres_${this.deck.id}` : "vq_pres_draft");
    try {
      localStorage.setItem(key, JSON.stringify(this.deck));
      localStorage.setItem("vq_pres_last_active", key);
      this.isDirty = false;
      this.lastSavedAt = new Date();
      return true;
    } catch (err) {
      console.warn("Could not save presentation to storage:", err);
      return false;
    }
  }

  loadFromStorage(storageKey = null) {
    const key = storageKey || localStorage.getItem("vq_pres_last_active") || "vq_pres_draft";
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return false;
      const data = JSON.parse(raw);
      this.deck = this._sanitizeDeck(data);
      this.undoStack = [];
      this.redoStack = [];
      this.isDirty = false;
      this._emit("change", { source: "storageLoad" });
      this._emit("slideChange", { activeIndex: this.deck.activeSlideIndex });
      return true;
    } catch (err) {
      console.warn("Could not load presentation from storage:", err);
      return false;
    }
  }

  loadFromDeck(data) {
    if (!data) return false;
    try {
      this.deck = this._sanitizeDeck(data);
      this.undoStack = [];
      this.redoStack = [];
      this.isDirty = false;
      this._emit("change", { source: "deckLoad" });
      this._emit("slideChange", { activeIndex: this.deck.activeSlideIndex || 0 });
      return true;
    } catch (err) {
      console.warn("Could not load presentation data:", err);
      return false;
    }
  }

  exportJSON() {
    return JSON.stringify(this.deck, null, 2);
  }

  exportMarkdown() {
    let md = `# ${this.deck.title}\n`;
    md += `*Theme: ${this.deck.theme} | Slides: ${this.deck.slides.length}*\n\n---\n\n`;

    this.deck.slides.forEach((slide, idx) => {
      md += `## Slide ${idx + 1}: ${slide.title || "Untitled"}\n`;
      if (slide.kicker) md += `**${slide.kicker}**\n\n`;
      if (slide.subtitle) md += `> ${slide.subtitle}\n\n`;

      if (slide.bullets && slide.bullets.length) {
        slide.bullets.forEach(b => { md += `- ${b}\n`; });
        md += "\n";
      }

      if (slide.cards && slide.cards.length) {
        slide.cards.forEach(c => {
          md += `### ${c.title || "Insight"} [${c.tag || "Pillar"}]\n${c.desc || ""}\n\n`;
        });
      }

      if (slide.metrics && slide.metrics.length) {
        slide.metrics.forEach(m => {
          md += `* **${m.num}** — ${m.label} (${m.note || ""})\n`;
        });
        md += "\n";
      }

      if (slide.events && slide.events.length) {
        slide.events.forEach(e => {
          md += `* **[${e.date}] ${e.title}**: ${e.desc} *(${e.source || ""})*\n`;
        });
        md += "\n";
      }

      if (slide.people && slide.people.length) {
        slide.people.forEach(p => {
          md += `* **${p.name}** — ${p.role}: ${p.note || ""}\n`;
        });
        md += "\n";
      }

      if (slide.actionItems && slide.actionItems.length) {
        md += `#### Action Checklist:\n`;
        slide.actionItems.forEach(a => { md += `[ ] ${a}\n`; });
        md += "\n";
      }

      if (slide.takeaway) {
        md += `**Takeaway:** ${slide.takeaway}\n\n`;
      }

      md += `---\n\n`;
    });

    return md;
  }

  setDeck(deckData) {
    if (!deckData) return;
    this._pushSnapshot();
    this.deck = this._sanitizeDeck(deckData);
    this.isDirty = false;
    this.lastSavedAt = new Date();
    this._emit("change", { source: "setDeck" });
    this._emit("slideChange", { activeIndex: this.deck.activeSlideIndex });
  }

  _sanitizeDeck(data) {
    if (!data || typeof data !== "object") return this._createDefaultDeck();
    const deck = Object.assign({}, data);
    deck.id = deck.id || deck.presentation_id || "pres_" + Math.random().toString(36).substr(2, 9);
    deck.presentation_id = deck.id;
    deck.title = deck.title || "Meeting Presentation";
    deck.theme = PresentationState.THEMES.some(t => t.id === deck.theme) ? deck.theme : "navy";
    deck.config = Object.assign({
      title: deck.title,
      slideCount: Array.isArray(deck.slides) ? deck.slides.length : 7,
      audience: "Executive Leadership",
      purpose: "Strategic Partnership",
      tone: "professional",
      theme: deck.theme,
      detailLevel: "balanced",
      topicsInclude: ["overview", "leadership", "developments", "strategy", "questions", "risks", "next_steps"],
      topicsExclude: ["speculation"]
    }, deck.config || {});

    deck.slides = Array.isArray(deck.slides) && deck.slides.length ? deck.slides.map((s, idx) => {
      const slide = Object.assign({}, s);
      slide.id = slide.id || slide.slide_id || `slide_${idx + 1}`;
      slide.slide_id = slide.id;
      return slide;
    }) : this._buildDefault7Slides("Acme Corp", "Strategic Partnership");

    deck.activeSlideIndex = (typeof deck.activeSlideIndex === "number" && deck.activeSlideIndex >= 0 && deck.activeSlideIndex < deck.slides.length)
      ? deck.activeSlideIndex
      : (typeof deck.active_slide_index === "number" && deck.active_slide_index >= 0 && deck.active_slide_index < deck.slides.length)
        ? deck.active_slide_index
        : 0;
    deck.selectedElement = null;
    return deck;
  }
}

if (typeof window !== "undefined") {
  window.PresentationState = PresentationState;
}
