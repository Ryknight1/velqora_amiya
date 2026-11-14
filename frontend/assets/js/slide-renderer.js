/* ============================================================
   VelQora Slide Renderer — Reusable Presentation HTML/CSS Engine
   Renders true 16:9 semantic presentation DOM for:
   - Center Editor Canvas (interactive, selectable elements)
   - Right Navigator Thumbnails (scaled miniature live preview)
   - Fullscreen Preview Player
   - High-resolution Print / PDF Export
   ============================================================ */

class SlideRenderer {
  static esc(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /* ---------------- Main Canvas Renderer ---------------- */
  static renderCanvas(slide, theme = "navy", selectedField = null, isInteractive = true) {
    if (!slide) return `<div class="empty-slide-msg">No slide selected</div>`;

    const themeClass = `theme-${theme || "navy"}`;
    const layout = slide.layout || "cards";

    let layoutHtml = "";
    switch (layout) {
      case "title":
        layoutHtml = this._renderTitleLayout(slide, selectedField, isInteractive);
        break;
      case "split":
        layoutHtml = this._renderSplitLayout(slide, selectedField, isInteractive);
        break;
      case "metrics":
        layoutHtml = this._renderMetricsLayout(slide, selectedField, isInteractive);
        break;
      case "timeline":
        layoutHtml = this._renderTimelineLayout(slide, selectedField, isInteractive);
        break;
      case "leadership":
        layoutHtml = this._renderLeadershipLayout(slide, selectedField, isInteractive);
        break;
      case "conclusion":
        layoutHtml = this._renderConclusionLayout(slide, selectedField, isInteractive);
        break;
      case "cards":
      default:
        layoutHtml = this._renderCardsLayout(slide, selectedField, isInteractive);
        break;
    }

    const footerText = slide.footer || "VelQora Intelligence • Source Grounded";

    return `
      <div class="slide-stage ${themeClass} layout-${layout}" data-layout="${layout}">
        <div class="slide-background-decor"></div>
        <div class="slide-inner">
          ${layoutHtml}
        </div>
        <div class="slide-footer-bar">
          <span class="slide-footer-text ${selectedField === "footer" ? "is-selected-el" : ""}"
                data-field="footer"
                ${isInteractive ? 'contenteditable="true" spellcheck="false"' : ""}>${this.esc(footerText)}</span>
          <span class="slide-footer-brand">VelQora AI</span>
        </div>
      </div>
    `;
  }

  /* ---------------- Miniature Thumbnail Renderer ---------------- */
  static renderThumbnail(slide, theme = "navy", index = 1, isSelected = false) {
    if (!slide) return "";
    const themeClass = `theme-${theme || "navy"}`;
    const layout = slide.layout || "cards";

    // Compact miniature representation for sharp 16:9 thumbnail rendering
    let miniContent = "";
    if (layout === "title") {
      miniContent = `
        <div class="mini-title-wrap">
          <div class="mini-kicker">${this.esc(slide.kicker || "Briefing")}</div>
          <div class="mini-title">${this.esc(slide.title || "Meeting Presentation")}</div>
          <div class="mini-sub">${this.esc(slide.subtitle || "")}</div>
        </div>
      `;
    } else if (layout === "metrics") {
      const items = (slide.metrics || []).slice(0, 4);
      miniContent = `
        <div class="mini-head">
          <span class="mini-kicker">${this.esc(slide.kicker || "Metrics")}</span>
          <span class="mini-title">${this.esc(slide.title || "Key Metrics")}</span>
        </div>
        <div class="mini-metrics-grid">
          ${items.map(m => `<div class="mini-metric"><b>${this.esc(m.num || "0")}</b><small>${this.esc(m.label || "")}</small></div>`).join("")}
        </div>
      `;
    } else if (layout === "timeline") {
      const items = (slide.events || []).slice(0, 3);
      miniContent = `
        <div class="mini-head">
          <span class="mini-kicker">${this.esc(slide.kicker || "Timeline")}</span>
          <span class="mini-title">${this.esc(slide.title || "Recent Developments")}</span>
        </div>
        <div class="mini-timeline-list">
          ${items.map(e => `<div class="mini-event"><span class="mini-dot"></span><small>${this.esc(e.title || "Milestone")}</small></div>`).join("")}
        </div>
      `;
    } else if (layout === "leadership") {
      const items = (slide.people || []).slice(0, 3);
      miniContent = `
        <div class="mini-head">
          <span class="mini-kicker">${this.esc(slide.kicker || "Leadership")}</span>
          <span class="mini-title">${this.esc(slide.title || "Key Stakeholders")}</span>
        </div>
        <div class="mini-people-grid">
          ${items.map(p => `<div class="mini-person"><b>${this.esc(p.name || "")}</b><small>${this.esc(p.role || "")}</small></div>`).join("")}
        </div>
      `;
    } else if (layout === "split") {
      miniContent = `
        <div class="mini-head">
          <span class="mini-kicker">${this.esc(slide.kicker || "Strategy")}</span>
          <span class="mini-title">${this.esc(slide.title || "Talking Points")}</span>
        </div>
        <div class="mini-split-row">
          <div class="mini-col-left"><span class="bar"></span><span class="bar"></span><span class="bar short"></span></div>
          <div class="mini-col-right"><div class="mini-card-box"></div></div>
        </div>
      `;
    } else if (layout === "conclusion") {
      miniContent = `
        <div class="mini-head">
          <span class="mini-kicker">${this.esc(slide.kicker || "Strategy")}</span>
          <span class="mini-title">${this.esc(slide.title || "Next Steps")}</span>
        </div>
        <div class="mini-checklist">
          <div class="mini-check-line"><span class="chk">✓</span><span class="bar"></span></div>
          <div class="mini-check-line"><span class="chk">✓</span><span class="bar"></span></div>
          <div class="mini-check-line"><span class="chk">✓</span><span class="bar short"></span></div>
        </div>
      `;
    } else {
      // cards
      const items = (slide.cards || []).slice(0, 3);
      miniContent = `
        <div class="mini-head">
          <span class="mini-kicker">${this.esc(slide.kicker || "Overview")}</span>
          <span class="mini-title">${this.esc(slide.title || "Core Insights")}</span>
        </div>
        <div class="mini-cards-grid">
          ${items.map(c => `<div class="mini-card"><small>${this.esc(c.title || "Insight")}</small></div>`).join("")}
        </div>
      `;
    }

    return `
      <div class="thumb-mini-stage ${themeClass}">
        ${miniContent}
      </div>
    `;
  }

  /* ---------------- Preview & Print Renderer ---------------- */
  static renderPreview(slide, theme = "navy") {
    return this.renderCanvas(slide, theme, null, false);
  }

  /* ---------------- Layout Implementations ---------------- */

  // 1. Title Layout
  static _renderTitleLayout(slide, selectedField, isInteractive) {
    const kicker = slide.kicker || "Executive Briefing";
    const title = slide.title || "Meeting Presentation";
    const subtitle = slide.subtitle || "Turn research into decisive executive clarity.";

    return `
      <div class="layout-title-body">
        <div class="slide-kicker-pill ${selectedField === "kicker" ? "is-selected-el" : ""}"
             data-field="kicker"
             ${isInteractive ? 'contenteditable="true" spellcheck="false"' : ""}>${this.esc(kicker)}</div>
        <h1 class="slide-main-title ${selectedField === "title" ? "is-selected-el" : ""}"
            data-field="title"
            ${isInteractive ? 'contenteditable="true" spellcheck="false"' : ""}>${this.esc(title)}</h1>
        <p class="slide-main-lead ${selectedField === "subtitle" ? "is-selected-el" : ""}"
           data-field="subtitle"
           ${isInteractive ? 'contenteditable="true" spellcheck="false"' : ""}>${this.esc(subtitle)}</p>
      </div>
    `;
  }

  // 2. Cards Layout
  static _renderCardsLayout(slide, selectedField, isInteractive) {
    const kicker = slide.kicker || "Strategic Pillars";
    const title = slide.title || "Core Business Insights";
    const subtitle = slide.subtitle || "Key operational differentiators and market drivers.";
    const cards = (slide.cards && slide.cards.length) ? slide.cards : [
      { tag: "Pillar 01", title: "Market Traction", desc: "Demonstrated growth across enterprise client segments.", badge: "Verified" },
      { tag: "Pillar 02", title: "Technical Moat", desc: "Proprietary software platform delivering operational efficiency.", badge: "Moat" },
      { tag: "Pillar 03", title: "Commercial Synergies", desc: "Clear bilateral value creation through shared market access.", badge: "Strategic" }
    ];

    const cardsHtml = cards.map((c, i) => `
      <div class="slide-card ${selectedField === `card_${i}` ? "is-selected-el" : ""}" data-card-idx="${i}">
        <div class="slide-card-top">
          <span class="slide-card-tag" data-field="card_${i}_tag" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(c.tag || `Pillar 0${i + 1}`)}</span>
          <span class="slide-card-badge" data-field="card_${i}_badge" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(c.badge || "Verified")}</span>
        </div>
        <h3 class="slide-card-title" data-field="card_${i}_title" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(c.title || "Insight Title")}</h3>
        <p class="slide-card-desc" data-field="card_${i}_desc" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(c.desc || "Insight description and verified evidence.")}</p>
      </div>
    `).join("");

    return `
      <div class="layout-header">
        <span class="slide-kicker ${selectedField === "kicker" ? "is-selected-el" : ""}" data-field="kicker" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(kicker)}</span>
        <h2 class="slide-heading ${selectedField === "title" ? "is-selected-el" : ""}" data-field="title" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(title)}</h2>
        <p class="slide-subheading ${selectedField === "subtitle" ? "is-selected-el" : ""}" data-field="subtitle" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(subtitle)}</p>
      </div>
      <div class="cards-grid cols-${Math.min(cards.length, 3)}">
        ${cardsHtml}
      </div>
    `;
  }

  // 3. Two-Column Split Layout
  static _renderSplitLayout(slide, selectedField, isInteractive) {
    const kicker = slide.kicker || "Strategic Discussion";
    const title = slide.title || "Strategic Talking Points";
    const subtitle = slide.subtitle || "High-priority topics to lead the conversation.";
    const bullets = (slide.bullets && slide.bullets.length) ? slide.bullets : [
      "Establish mutual goals and validate business momentum.",
      "Address operational synergies and short-term milestones.",
      "Define measurable project deliverables and follow-up timeline."
    ];
    const highlightTitle = slide.highlightTitle || "Key Meeting Goal";
    const highlightBody = slide.highlightBody || "Anchor the discussion in mutual commercial ROI and verified capabilities.";

    const bulletsHtml = bullets.map((b, i) => `
      <li class="bullet-item" data-bullet-idx="${i}">
        <span class="bullet-icon">✦</span>
        <span class="bullet-text ${selectedField === `bullet_${i}` ? "is-selected-el" : ""}"
              data-field="bullet_${i}"
              ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(b)}</span>
      </li>
    `).join("");

    return `
      <div class="layout-header">
        <span class="slide-kicker ${selectedField === "kicker" ? "is-selected-el" : ""}" data-field="kicker" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(kicker)}</span>
        <h2 class="slide-heading ${selectedField === "title" ? "is-selected-el" : ""}" data-field="title" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(title)}</h2>
        <p class="slide-subheading ${selectedField === "subtitle" ? "is-selected-el" : ""}" data-field="subtitle" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(subtitle)}</p>
      </div>
      <div class="split-columns">
        <div class="split-col-narrative">
          <ul class="bullets-list">
            ${bulletsHtml}
          </ul>
        </div>
        <div class="split-col-callout">
          <div class="callout-card ${selectedField === "highlight" ? "is-selected-el" : ""}">
            <div class="callout-pill">Executive Focus</div>
            <h4 class="callout-title" data-field="highlightTitle" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(highlightTitle)}</h4>
            <p class="callout-body" data-field="highlightBody" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(highlightBody)}</p>
          </div>
        </div>
      </div>
    `;
  }

  // 4. Metrics & Stats Layout
  static _renderMetricsLayout(slide, selectedField, isInteractive) {
    const kicker = slide.kicker || "Quantitative Indicators";
    const title = slide.title || "Key Metrics & Verification Matrix";
    const subtitle = slide.subtitle || "Grounded figures verified across multi-source research.";
    const metrics = (slide.metrics && slide.metrics.length) ? slide.metrics : [
      { num: "94%", label: "Source Grounding", note: "Verified against multi-source evidence" },
      { num: "30-Day", label: "Research Window", note: "Recent verified market developments" },
      { num: "4.8x", label: "Enterprise Velocity", note: "Reported growth in target segments" },
      { num: "100%", label: "Deterministic Check", note: "Zero hallucinations in factual citations" }
    ];

    const metricsHtml = metrics.map((m, i) => `
      <div class="metric-card ${selectedField === `metric_${i}` ? "is-selected-el" : ""}">
        <div class="metric-value" data-field="metric_${i}_num" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(m.num || "0")}</div>
        <div class="metric-label" data-field="metric_${i}_label" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(m.label || "Metric")}</div>
        <div class="metric-note" data-field="metric_${i}_note" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(m.note || "")}</div>
      </div>
    `).join("");

    return `
      <div class="layout-header">
        <span class="slide-kicker ${selectedField === "kicker" ? "is-selected-el" : ""}" data-field="kicker" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(kicker)}</span>
        <h2 class="slide-heading ${selectedField === "title" ? "is-selected-el" : ""}" data-field="title" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(title)}</h2>
        <p class="slide-subheading ${selectedField === "subtitle" ? "is-selected-el" : ""}" data-field="subtitle" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(subtitle)}</p>
      </div>
      <div class="metrics-grid cols-${Math.min(metrics.length, 4)}">
        ${metricsHtml}
      </div>
    `;
  }

  // 5. Timeline Layout
  static _renderTimelineLayout(slide, selectedField, isInteractive) {
    const kicker = slide.kicker || "Market Velocity";
    const title = slide.title || "Recent Developments & Timeline";
    const subtitle = slide.subtitle || "Chronological timeline of verified developments and milestones.";
    const events = (slide.events && slide.events.length) ? slide.events : [
      { date: "Current Quarter", title: "Enterprise Service Expansion", desc: "Launched major expansion featuring enhanced automation and unified compliance.", source: "Press Announcement" },
      { date: "Last Month", title: "Strategic Ecosystem Alliances", desc: "Secured key partner integrations expanding addressable market penetration.", source: "Marketwire" },
      { date: "Recent", title: "Commercial Leadership Expansion", desc: "Strengthened executive team to accelerate enterprise go-to-market execution.", source: "Verified News" }
    ];

    const eventsHtml = events.map((e, i) => `
      <div class="timeline-item ${selectedField === `event_${i}` ? "is-selected-el" : ""}">
        <div class="timeline-marker">
          <span class="timeline-dot"></span>
          <span class="timeline-date" data-field="event_${i}_date" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(e.date || "Recent")}</span>
        </div>
        <div class="timeline-card">
          <h4 class="timeline-card-title" data-field="event_${i}_title" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(e.title || "Milestone")}</h4>
          <p class="timeline-card-desc" data-field="event_${i}_desc" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(e.desc || "")}</p>
          <div class="timeline-card-source">
            <span>Source:</span>
            <cite data-field="event_${i}_source" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(e.source || "Verified Source")}</cite>
          </div>
        </div>
      </div>
    `).join("");

    return `
      <div class="layout-header">
        <span class="slide-kicker ${selectedField === "kicker" ? "is-selected-el" : ""}" data-field="kicker" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(kicker)}</span>
        <h2 class="slide-heading ${selectedField === "title" ? "is-selected-el" : ""}" data-field="title" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(title)}</h2>
        <p class="slide-subheading ${selectedField === "subtitle" ? "is-selected-el" : ""}" data-field="subtitle" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(subtitle)}</p>
      </div>
      <div class="timeline-row">
        ${eventsHtml}
      </div>
    `;
  }

  // 6. Leadership Layout
  static _renderLeadershipLayout(slide, selectedField, isInteractive) {
    const kicker = slide.kicker || "Stakeholder Intelligence";
    const title = slide.title || "Key Leadership & Decision Makers";
    const subtitle = slide.subtitle || "Executive profiles and discussion counterparts identified in briefing.";
    const people = (slide.people && slide.people.length) ? slide.people : [
      { name: "Executive Leadership", role: "Key Decision Maker", note: "Sets strategic priorities, capital allocation, and organizational vision." },
      { name: "Product & Engineering", role: "Technology Leadership", note: "Oversees core innovation, technical roadmap, and system scalability." },
      { name: "Commercial & Alliances", role: "Partnership Stakeholder", note: "Manages partner evaluation, commercial contracts, and joint go-to-market." }
    ];

    const peopleHtml = people.map((p, i) => `
      <div class="people-card ${selectedField === `person_${i}` ? "is-selected-el" : ""}">
        <div class="people-avatar">${this.esc(p.name ? p.name.split(" ").map(w => w[0]).join("").slice(0, 2) : "VQ")}</div>
        <div class="people-info">
          <h3 class="people-name" data-field="person_${i}_name" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(p.name || "Leader Name")}</h3>
          <p class="people-role" data-field="person_${i}_role" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(p.role || "Executive Role")}</p>
          <p class="people-note" data-field="person_${i}_note" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(p.note || "")}</p>
        </div>
      </div>
    `).join("");

    return `
      <div class="layout-header">
        <span class="slide-kicker ${selectedField === "kicker" ? "is-selected-el" : ""}" data-field="kicker" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(kicker)}</span>
        <h2 class="slide-heading ${selectedField === "title" ? "is-selected-el" : ""}" data-field="title" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(title)}</h2>
        <p class="slide-subheading ${selectedField === "subtitle" ? "is-selected-el" : ""}" data-field="subtitle" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(subtitle)}</p>
      </div>
      <div class="people-grid cols-${Math.min(people.length, 3)}">
        ${peopleHtml}
      </div>
    `;
  }

  // 7. Conclusion & Next Steps Layout
  static _renderConclusionLayout(slide, selectedField, isInteractive) {
    const kicker = slide.kicker || "Meeting Strategy";
    const title = slide.title || "Strategic Takeaways & Action Plan";
    const subtitle = slide.subtitle || "Prioritized roadmap to drive alignment and concrete next steps.";
    const items = (slide.actionItems && slide.actionItems.length) ? slide.actionItems : [
      "Open by anchoring on verified recent developments to build immediate credibility.",
      "Address key strategic questions and partnership risks with transparent solutions.",
      "Conclude by securing commitment on clear ownership and next milestone date."
    ];
    const takeaway = slide.takeaway || "Be ready for what matters: enter every conversation equipped with verified intelligence.";

    const itemsHtml = items.map((a, i) => `
      <div class="action-row ${selectedField === `action_${i}` ? "is-selected-el" : ""}">
        <span class="action-check">✓</span>
        <p class="action-text" data-field="action_${i}" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(a)}</p>
      </div>
    `).join("");

    return `
      <div class="layout-header">
        <span class="slide-kicker ${selectedField === "kicker" ? "is-selected-el" : ""}" data-field="kicker" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(kicker)}</span>
        <h2 class="slide-heading ${selectedField === "title" ? "is-selected-el" : ""}" data-field="title" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(title)}</h2>
        <p class="slide-subheading ${selectedField === "subtitle" ? "is-selected-el" : ""}" data-field="subtitle" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(subtitle)}</p>
      </div>
      <div class="conclusion-wrap">
        <div class="action-checklist">
          ${itemsHtml}
        </div>
        <div class="takeaway-banner ${selectedField === "takeaway" ? "is-selected-el" : ""}">
          <span class="takeaway-tag">Core Takeaway</span>
          <p class="takeaway-text" data-field="takeaway" ${isInteractive ? 'contenteditable="true"' : ""}>${this.esc(takeaway)}</p>
        </div>
      </div>
    `;
  }
}

if (typeof window !== "undefined") {
  window.SlideRenderer = SlideRenderer;
}
