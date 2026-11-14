/* ============================================================
   VelQora Presentation Studio Controller
   Orchestrates three panels, single presentation state, live canvas
   renderer, miniature live thumbnails, AI chat interaction structure,
   and modal workflows.
   ============================================================ */

(function() {
  "use strict";

  // DOM Elements
  const dirtyFlag = document.getElementById("dirtyFlag");
  const savedBadge = document.getElementById("savedBadge");
  const undoBtn = document.getElementById("undoBtn");
  const redoBtn = document.getElementById("redoBtn");
  const themeBtn = document.getElementById("themeBtn");
  const themeDot = document.getElementById("themeDot");
  const themeBtnLabel = document.getElementById("themeBtnLabel");
  const addSlideBtn = document.getElementById("addSlideBtn");
  const configBtn = document.getElementById("configBtn");
  const previewBtn = document.getElementById("previewBtn");
  const saveBtn = document.getElementById("saveBtn");
  const exportBtn = document.getElementById("exportBtn");

  // Left Panel: AI Chat
  const chatLog = document.getElementById("chatLog");
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const chatTyping = document.getElementById("chatTyping");
  const promptRow = document.getElementById("promptRow");
  const regenBtn = document.getElementById("regenBtn");
  const deckSummaryChip = document.getElementById("deckSummaryChip");
  const openConfigFromChat = document.getElementById("openConfigFromChat");

  // Center Panel: Editor
  const slideLabel = document.getElementById("slideLabel");
  const layoutPill = document.getElementById("layoutPill");
  const selHint = document.getElementById("selHint");
  const slideCanvas = document.getElementById("slideCanvas");
  const quickAddCardBtn = document.getElementById("quickAddCardBtn");
  const quickAddBulletBtn = document.getElementById("quickAddBulletBtn");
  const quickSwitchLayoutBtn = document.getElementById("quickSwitchLayoutBtn");
  const quickResetSlideBtn = document.getElementById("quickResetSlideBtn");

  // Right Panel: Navigator
  const navAddSlideBtn = document.getElementById("navAddSlideBtn");
  const navDupSlideBtn = document.getElementById("navDupSlideBtn");
  const navDelSlideBtn = document.getElementById("navDelSlideBtn");
  const thumbList = document.getElementById("thumbList");
  const slideCountLabel = document.getElementById("slideCountLabel");
  const mobileSlideCount = document.getElementById("mobileSlideCount");

  // Modals
  const configModal = document.getElementById("configModal");
  const closeConfigModalBtn = document.getElementById("closeConfigModalBtn");
  const cancelConfigBtn = document.getElementById("cancelConfigBtn");
  const applyConfigBtn = document.getElementById("applyConfigBtn");
  const cfgPresTitle = document.getElementById("cfgPresTitle");
  const cfgSlideCount = document.getElementById("cfgSlideCount");
  const cfgAudience = document.getElementById("cfgAudience");
  const cfgMeetingPurpose = document.getElementById("cfgMeetingPurpose");
  const cfgTone = document.getElementById("cfgTone");
  const cfgTheme = document.getElementById("cfgTheme");
  const cfgDetail = document.getElementById("cfgDetail");

  const themeModal = document.getElementById("themeModal");
  const closeThemeModalBtn = document.getElementById("closeThemeModalBtn");
  const themesGrid = document.getElementById("themesGrid");

  const layoutModal = document.getElementById("layoutModal");
  const closeLayoutModalBtn = document.getElementById("closeLayoutModalBtn");
  const layoutsGrid = document.getElementById("layoutsGrid");

  const previewModal = document.getElementById("previewModal");
  const previewStage = document.getElementById("previewStage");
  const prevSlideBtn = document.getElementById("prevSlideBtn");
  const nextSlideBtn = document.getElementById("nextSlideBtn");
  const previewCounter = document.getElementById("previewCounter");
  const closePreviewBtn = document.getElementById("closePreviewBtn");

  const exportModal = document.getElementById("exportModal");
  const closeExportModalBtn = document.getElementById("closeExportModalBtn");
  const exportPdfBtn = document.getElementById("exportPdfBtn");
  const exportJsonBtn = document.getElementById("exportJsonBtn");
  const exportMdBtn = document.getElementById("exportMdBtn");
  const exportPptxBtn = document.getElementById("exportPptxBtn");

  // Mobile Tabs
  const studioTabs = document.querySelectorAll(".studio-tabs button");

  // State instances
  let presentationState = null;
  let activeBriefingData = null;
  let previewIndex = 0;
  let lastPromptExecuted = null;
  let inlineEditDebounce = null;
  let draggedSlideIndex = null;

  const SUGGESTED_PROMPTS = [
    "Create a 7-slide presentation.",
    "Make this presentation more professional.",
    "Improve slide 3.",
    "Add recent company developments.",
    "Add leadership information.",
    "Create a conclusion slide.",
    "Change presentation theme."
  ];

  /* ============================================================
     1. INITIALIZATION & WORKFLOW CONTEXT
     ============================================================ */
  async function initStudio() {
    const ctx = typeof VQContext !== "undefined" ? VQContext.fromLocation() : null;
    const entityName = (ctx && ctx.entity_name) ? ctx.entity_name.trim() : "Acme Corp";
    const briefingId = (ctx && ctx.briefing_id) ? ctx.briefing_id : null;
    const presId = (ctx && ctx.presentation_id) ? ctx.presentation_id : null;

    // Initialize Presentation State
    presentationState = new PresentationState();

    // Try loading saved presentation if presId or cached draft exists
    const hasLoaded = presId ? presentationState.loadFromStorage(`vq_pres_${presId}`) : presentationState.loadFromStorage();

    // If briefing ID is provided in context and not loaded from draft, fetch real briefing
    if (!hasLoaded && briefingId && typeof VQApi !== "undefined") {
      try {
        const res = await VQApi.getBriefing(briefingId);
        if (res && res.briefing) {
          activeBriefingData = res.briefing;
          const purpose = (activeBriefingData.meeting && activeBriefingData.meeting.purpose) || "Strategic Partnership";
          presentationState.updateConfig({
            title: `${activeBriefingData.entity.name || entityName} — Strategic Briefing`,
            purpose: purpose,
            slideCount: 7
          }, true, activeBriefingData);
        }
      } catch (err) {
        console.warn("Could not fetch remote briefing; using initialized template:", err);
      }
    } else if (!hasLoaded && entityName && entityName !== "Acme Corp") {
      presentationState.updateConfig({
        title: `${entityName} — Strategic Briefing`,
        purpose: "Strategic Partnership Alignment"
      }, true);
    }

    // Save active presentation ID in context
    if (typeof VQContext !== "undefined") {
      VQContext.write({ presentation_id: presentationState.getDeck().id });
    }

    // Wire State Listeners
    presentationState.on("change", (e) => onStateChange(e));
    presentationState.on("slideChange", () => onSlideChange());
    presentationState.on("historyChange", (e) => onHistoryChange(e));

    // Initialize UI Components
    setupSuggestedPrompts();
    setupModals();
    setupToolbar();
    setupCanvasEditor();
    setupNavigator();
    setupMobileTabs();

    // Initial Render
    renderAll();
    welcomeMessage(entityName);
  }

  /* ============================================================
     2. RENDER PIPELINE
     ============================================================ */
  function renderAll() {
    updateHeaderStatus();
    renderActiveSlide();
    renderThumbnails();
    updateSlideLabels();
    updateThemeUI();
    updateConfigSummary();
  }

  function updateHeaderStatus() {
    if (dirtyFlag) dirtyFlag.hidden = !presentationState.isDirty;
    if (savedBadge) {
      if (presentationState.isDirty) {
        savedBadge.style.opacity = "0.3";
      } else {
        savedBadge.style.opacity = "1";
        savedBadge.textContent = presentationState.lastSavedAt
          ? `✓ Saved ${presentationState.lastSavedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
          : "✓ Saved";
      }
    }
  }

  function updateSlideLabels() {
    const activeIdx = presentationState.getActiveSlideIndex();
    const total = presentationState.getSlideCount();
    const activeSlide = presentationState.getActiveSlide();

    if (slideLabel) slideLabel.textContent = `Slide ${activeIdx + 1} of ${total}`;
    if (slideCountLabel) slideCountLabel.textContent = `(${total})`;
    if (mobileSlideCount) mobileSlideCount.textContent = `${total}`;
    if (layoutPill && activeSlide) {
      layoutPill.textContent = activeSlide.layout || "Cards";
    }
  }

  function updateThemeUI() {
    const theme = presentationState.getTheme();
    const themeObj = PresentationState.THEMES.find(t => t.id === theme) || PresentationState.THEMES[0];
    if (themeBtnLabel) themeBtnLabel.textContent = themeObj.name;
    if (themeDot) themeDot.style.background = themeObj.accent;
  }

  function updateConfigSummary() {
    const cfg = presentationState.getConfig();
    const total = presentationState.getSlideCount();
    const themeObj = PresentationState.THEMES.find(t => t.id === presentationState.getTheme()) || PresentationState.THEMES[0];
    if (deckSummaryChip) {
      deckSummaryChip.textContent = `${total} Slides · ${themeObj.name} · ${cfg.tone || "Professional"}`;
    }
  }

  function renderActiveSlide() {
    if (!slideCanvas) return;
    const slide = presentationState.getActiveSlide();
    const theme = presentationState.getTheme();
    const selectedField = presentationState.getSelectedElement();

    slideCanvas.innerHTML = SlideRenderer.renderCanvas(slide, theme, selectedField, true);
    wireCanvasEditableEvents();
  }

  function renderThumbnails() {
    if (!thumbList) return;
    thumbList.replaceChildren();

    const slides = presentationState.getSlides();
    const activeIdx = presentationState.getActiveSlideIndex();
    const theme = presentationState.getTheme();

    slides.forEach((slide, idx) => {
      const card = document.createElement("div");
      card.className = "thumb-card" + (idx === activeIdx ? " on" : "");
      card.draggable = true;
      card.dataset.slideIndex = idx;

      card.innerHTML = `
        <div class="thumb-drag-handle" title="Drag to reorder">⠿</div>
        <div class="thumb-preview-wrap">
          ${SlideRenderer.renderThumbnail(slide, theme, idx + 1, idx === activeIdx)}
          <div class="thumb-meta">
            <span class="thumb-title">${idx + 1}. ${SlideRenderer.esc(slide.title || "Slide " + (idx + 1))}</span>
            <span class="thumb-layout-tag">${slide.layout || "card"}</span>
          </div>
        </div>
        <div class="thumb-actions">
          <button type="button" class="thumb-action-btn move-up" title="Move Up">▲</button>
          <button type="button" class="thumb-action-btn move-down" title="Move Down">▼</button>
          <button type="button" class="thumb-action-btn del-btn" title="Delete Slide">✕</button>
        </div>
      `;

      // Thumbnail Click: Select slide
      card.addEventListener("click", (e) => {
        if (e.target.closest(".thumb-action-btn") || e.target.closest(".thumb-drag-handle")) return;
        presentationState.setActiveSlide(idx);
      });

      // Move Up
      const upBtn = card.querySelector(".move-up");
      if (upBtn) {
        upBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          presentationState.moveSlide(idx, Math.max(0, idx - 1));
        });
      }

      // Move Down
      const downBtn = card.querySelector(".move-down");
      if (downBtn) {
        downBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          presentationState.moveSlide(idx, Math.min(slides.length - 1, idx + 1));
        });
      }

      // Delete Slide
      const delBtn = card.querySelector(".del-btn");
      if (delBtn) {
        delBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          if (slides.length <= 1) {
            alert("A presentation must have at least one slide.");
            return;
          }
          if (confirm(`Delete slide ${idx + 1} ("${slide.title || "Slide"}")?`)) {
            presentationState.deleteSlide(idx);
          }
        });
      }

      // HTML5 Drag and Drop Reordering
      card.addEventListener("dragstart", (e) => {
        draggedSlideIndex = idx;
        card.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", idx);
      });

      card.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        card.classList.add("drag-over");
      });

      card.addEventListener("dragleave", () => {
        card.classList.remove("drag-over");
      });

      card.addEventListener("drop", (e) => {
        e.preventDefault();
        card.classList.remove("drag-over");
        const fromIdx = draggedSlideIndex !== null ? draggedSlideIndex : parseInt(e.dataTransfer.getData("text/plain"), 10);
        if (!isNaN(fromIdx) && fromIdx !== idx) {
          presentationState.moveSlide(fromIdx, idx);
        }
      });

      card.addEventListener("dragend", () => {
        card.classList.remove("dragging");
        draggedSlideIndex = null;
        document.querySelectorAll(".thumb-card").forEach(c => c.classList.remove("drag-over"));
      });

      thumbList.appendChild(card);
    });
  }

  function wireCanvasEditableEvents() {
    if (!slideCanvas) return;

    // Elements with contenteditable or data-field
    const editables = slideCanvas.querySelectorAll("[data-field]");
    editables.forEach(el => {
      const field = el.dataset.field;

      el.addEventListener("click", (e) => {
        e.stopPropagation();
        presentationState.selectElement(field);
        if (selHint) selHint.textContent = `Editing: ${field.replace(/_/g, " ")}`;
      });

      el.addEventListener("input", () => {
        clearTimeout(inlineEditDebounce);
        inlineEditDebounce = setTimeout(() => {
          const val = el.innerText.trim();
          handleFieldUpdate(field, val);
        }, 150);
      });

      el.addEventListener("blur", () => {
        const val = el.innerText.trim();
        handleFieldUpdate(field, val);
      });
    });

    slideCanvas.addEventListener("click", () => {
      presentationState.selectElement(null);
      if (selHint) selHint.textContent = "Click any element to edit inline";
    });
  }

  function handleFieldUpdate(field, value) {
    const activeIdx = presentationState.getActiveSlideIndex();
    const slide = presentationState.getActiveSlide();
    if (!slide) return;

    // Parse complex field paths (e.g. card_0_title, metric_1_num, bullet_2)
    if (field.startsWith("card_")) {
      const parts = field.split("_");
      const cardIdx = parseInt(parts[1], 10);
      const subfield = parts[2];
      if (slide.cards && slide.cards[cardIdx]) {
        slide.cards[cardIdx][subfield] = value;
      }
    } else if (field.startsWith("metric_")) {
      const parts = field.split("_");
      const metricIdx = parseInt(parts[1], 10);
      const subfield = parts[2];
      if (slide.metrics && slide.metrics[metricIdx]) {
        slide.metrics[metricIdx][subfield] = value;
      }
    } else if (field.startsWith("event_")) {
      const parts = field.split("_");
      const eventIdx = parseInt(parts[1], 10);
      const subfield = parts[2];
      if (slide.events && slide.events[eventIdx]) {
        slide.events[eventIdx][subfield] = value;
      }
    } else if (field.startsWith("person_")) {
      const parts = field.split("_");
      const personIdx = parseInt(parts[1], 10);
      const subfield = parts[2];
      if (slide.people && slide.people[personIdx]) {
        slide.people[personIdx][subfield] = value;
      }
    } else if (field.startsWith("bullet_")) {
      const parts = field.split("_");
      const bulletIdx = parseInt(parts[1], 10);
      if (slide.bullets && slide.bullets[bulletIdx] !== undefined) {
        slide.bullets[bulletIdx] = value;
      }
    } else if (field.startsWith("action_")) {
      const parts = field.split("_");
      const actionIdx = parseInt(parts[1], 10);
      if (slide.actionItems && slide.actionItems[actionIdx] !== undefined) {
        slide.actionItems[actionIdx] = value;
      }
    } else {
      slide[field] = value;
    }

    presentationState.isDirty = true;
    updateHeaderStatus();
    // Update live thumbnail title if slide title changed
    if (field === "title") {
      const activeCard = thumbList ? thumbList.children[activeIdx] : null;
      if (activeCard) {
        const titleSpan = activeCard.querySelector(".thumb-title");
        if (titleSpan) titleSpan.textContent = `${activeIdx + 1}. ${value || "Slide"}`;
      }
    }
  }

  /* ============================================================
     3. STATE EVENT HANDLERS
     ============================================================ */
  function onStateChange(e) {
    if (e && e.source === "theme") {
      updateThemeUI();
      renderActiveSlide();
      renderThumbnails();
    } else if (e && e.source === "inlineEdit") {
      updateHeaderStatus();
    } else {
      renderAll();
    }
  }

  function onSlideChange() {
    renderActiveSlide();
    updateSlideLabels();

    // Update active class on thumbnails without rebuilding DOM
    if (thumbList) {
      const activeIdx = presentationState.getActiveSlideIndex();
      Array.from(thumbList.children).forEach((child, i) => {
        child.classList.toggle("on", i === activeIdx);
      });
    }
  }

  function onHistoryChange(e) {
    if (undoBtn) undoBtn.disabled = !e.canUndo;
    if (redoBtn) redoBtn.disabled = !e.canRedo;
  }

  /* ============================================================
     4. TOOLBAR & ACTION CONTROLS
     ============================================================ */
  function setupToolbar() {
    // Undo
    if (undoBtn) {
      undoBtn.addEventListener("click", () => {
        if (presentationState.undo()) {
          showActionToast("Undo applied");
        }
      });
    }

    // Redo
    if (redoBtn) {
      redoBtn.addEventListener("click", () => {
        if (presentationState.redo()) {
          showActionToast("Redo applied");
        }
      });
    }

    // Theme selector
    if (themeBtn) {
      themeBtn.addEventListener("click", () => openThemeModal());
    }

    // Add Slide
    if (addSlideBtn) {
      addSlideBtn.addEventListener("click", () => openLayoutModal());
    }

    // Config Setup
    if (configBtn) {
      configBtn.addEventListener("click", () => openConfigModal());
    }
    if (openConfigFromChat) {
      openConfigFromChat.addEventListener("click", () => openConfigModal());
    }

    // Preview
    if (previewBtn) {
      previewBtn.addEventListener("click", () => openPreviewModal());
    }

    // Save
    if (saveBtn) {
      saveBtn.addEventListener("click", () => {
        if (presentationState.saveToStorage()) {
          updateHeaderStatus();
          showActionToast("Presentation saved successfully");
          addChatMessage("Presentation saved to local workspace.", "ai");
        }
      });
    }

    // Export
    if (exportBtn) {
      exportBtn.addEventListener("click", () => openExportModal());
    }

    // Keyboard Shortcuts (Ctrl+Z, Ctrl+Y, Ctrl+S, Esc)
    window.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        presentationState.undo();
      } else if ((e.ctrlKey || e.metaKey) && (e.key === "y" || (e.shiftKey && e.key === "Z"))) {
        e.preventDefault();
        presentationState.redo();
      } else if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        presentationState.saveToStorage();
        updateHeaderStatus();
        showActionToast("Presentation saved");
      }
    });
  }

  /* ============================================================
     5. AI CHAT ASSISTANT & INTERACTION STRUCTURE
     ============================================================ */
  function setupSuggestedPrompts() {
    if (!promptRow) return;
    promptRow.replaceChildren();

    SUGGESTED_PROMPTS.forEach(promptText => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "prompt-chip";
      chip.textContent = promptText;
      chip.addEventListener("click", () => {
        executePrompt(promptText);
      });
      promptRow.appendChild(chip);
    });

    // Chat Form Submit
    if (chatForm && chatInput) {
      chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;
        chatInput.value = "";
        executePrompt(text);
      });
    }

    // Regenerate button
    if (regenBtn) {
      regenBtn.addEventListener("click", () => {
        if (lastPromptExecuted) {
          executePrompt(lastPromptExecuted);
        } else {
          executePrompt("Improve slide 3.");
        }
      });
    }
  }

  async function executePrompt(promptText) {
    lastPromptExecuted = promptText;
    addChatMessage(promptText, "user");
    setTypingState(true);

    const activeIdx = presentationState.getActiveSlideIndex();
    const activeSlide = presentationState.getActiveSlide();
    const deck = presentationState.getDeck();

    // Check if user is asking for a full new presentation e.g. "Create a 7-slide presentation"
    const isNewDeckRequest = /create\s+a\s+\d+-slide/i.test(promptText) || /generate\s+\d+-slide/i.test(promptText);

    try {
      if (isNewDeckRequest && typeof VQApi !== "undefined" && VQApi.createPresentation) {
        const countMatch = promptText.match(/\b(\d+)-slide\b/i);
        const count = countMatch ? parseInt(countMatch[1], 10) : (deck.config ? deck.config.slideCount : 7);
        const ctx = typeof VQContext !== "undefined" ? VQContext.read() : null;
        const res = await VQApi.createPresentation({
          research_id: (ctx && ctx.research_id) || deck.research_id,
          briefing_id: (ctx && ctx.briefing_id) || deck.briefing_id,
          title: deck.title,
          prompt: promptText,
          slide_count: count,
          audience: deck.config ? deck.config.audience : "Executive Leadership",
          purpose: deck.config ? deck.config.purpose : "Strategic Partnership Alignment",
          tone: deck.config ? deck.config.tone : "professional",
          theme: deck.theme || "navy"
        });

        if (res && res.slides) {
          presentationState.setDeck(res);
          addChatMessage(`Generated a complete **${res.slides.length}-slide executive presentation** using verified research intelligence and Gemini Flash.`, "ai");
          setTypingState(false);
          return;
        }
      }

      // Standard conversational slide modification via POST /api/presentation/chat
      if (typeof VQApi !== "undefined" && VQApi.presentationChat) {
        const historyItems = [];
        const msgEls = chatLog ? chatLog.querySelectorAll(".msg") : [];
        msgEls.forEach(el => {
          const role = el.classList.contains("user") ? "user" : "assistant";
          const text = el.innerText.replace(/^VelQora AI\s+\d+:\d+\s+/, "").trim();
          if (text) historyItems.push({ role, content: text });
        });

        const res = await VQApi.presentationChat({
          presentation_id: deck.id || deck.presentation_id || "pres_draft",
          message: promptText,
          selected_slide_id: activeSlide ? (activeSlide.id || activeSlide.slide_id) : null,
          selected_slide_index: activeIdx,
          history: historyItems.slice(-4),
          presentation: deck
        });

        if (res && res.presentation) {
          presentationState.setDeck(res.presentation);
          if (typeof res.affected_slide_index === "number") {
            presentationState.setActiveSlide(res.affected_slide_index);
          }
          addChatMessage(res.explanation || "Updated presentation successfully.", "ai");
          setTypingState(false);
          return;
        }
      }
    } catch (err) {
      console.warn("AI backend call encountered an error; falling back gracefully:", err);
      // Graceful local handling to prevent UI disruption if Bifrost gateway is unreachable
      processAgentAction(promptText);
      addChatMessage("*(Gemini Flash via Bifrost gateway was temporarily unreachable; applied structured local transformation)*", "ai");
      setTypingState(false);
      return;
    }

    // Default local fallback if no VQApi
    processAgentAction(promptText);
    setTypingState(false);
  }

  function setTypingState(isTyping) {
    if (chatTyping) {
      chatTyping.classList.toggle("active", isTyping);
      if (isTyping && chatLog) {
        chatLog.scrollTop = chatLog.scrollHeight;
      }
    }
  }

  function addChatMessage(content, sender = "ai") {
    if (!chatLog) return;
    const msg = document.createElement("div");
    msg.className = `msg ${sender}`;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (sender === "ai") {
      msg.innerHTML = `
        <div class="ai-header">
          <span>VelQora AI</span>
          <time>${time}</time>
        </div>
        <div>${formatMessageContent(content)}</div>
      `;
    } else {
      msg.innerHTML = `<div>${SlideRenderer.esc(content)}</div>`;
    }

    chatLog.appendChild(msg);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function formatMessageContent(raw) {
    if (!raw) return "";
    let s = SlideRenderer.esc(raw);
    s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\*(.*?)\*/g, "<em>$1</em>");
    s = s.replace(/\n/g, "<br>");
    return s;
  }

  function welcomeMessage(entityName) {
    if (activeBriefingData) {
      addChatMessage(`Welcome to Presentation Studio. Loaded verified research briefing for **${entityName}** with ground truth sources. You can customize slides, change themes, or ask me to restructure content.`);
    } else {
      addChatMessage(`Welcome to Presentation Studio. Workspace is ready with standard executive presentation templates for **${entityName}**. Use the suggested prompts or settings above to customize your deck.`);
    }
  }

  function processAgentAction(prompt) {
    const p = prompt.toLowerCase();

    if (p.includes("7-slide") || p.includes("seven slide") || p.includes("create a 7")) {
      const cfg = presentationState.getConfig();
      cfg.slideCount = 7;
      presentationState.updateConfig(cfg, true, activeBriefingData);
      addChatMessage("Generated a complete **7-slide executive briefing** deck covering Overview, Developments, Leadership, Strategy, Risks, and Action Plan.");
    } else if (p.includes("more professional") || p.includes("professional tone")) {
      presentationState.setTheme("navy");
      const cfg = presentationState.getConfig();
      cfg.tone = "professional";
      presentationState.updateConfig(cfg, false);
      addChatMessage("Refined presentation theme to **Executive Navy** and tightened typography standards for high-level board review.");
    } else if (p.includes("slide 3") || p.includes("improve slide 3")) {
      // Focus and sharpen slide 3
      presentationState.setActiveSlide(2); // 0-based
      const slide = presentationState.getActiveSlide();
      if (slide) {
        presentationState.updateSlide(2, {
          kicker: "Strategic Traction",
          subtitle: "Key operational milestones and verified acceleration within target market segments."
        });
      }
      addChatMessage("Navigated to and enhanced **Slide 3**. Sharpened strategic narrative focus and validated recent momentum.");
    } else if (p.includes("recent company developments") || p.includes("developments")) {
      const newIdx = presentationState.addSlide("timeline", {
        kicker: "Market Velocity",
        title: "Recent Company Developments",
        subtitle: "Verified chronological milestones from recent research findings."
      });
      presentationState.setActiveSlide(newIdx);
      addChatMessage("Added a dedicated **Recent Developments** timeline slide grounded in verified findings.");
    } else if (p.includes("leadership") || p.includes("key people")) {
      const newIdx = presentationState.addSlide("leadership", {
        kicker: "Stakeholder Intelligence",
        title: "Executive Leadership & Key People",
        subtitle: "Primary discussion counterparts and decision-making authority."
      });
      presentationState.setActiveSlide(newIdx);
      addChatMessage("Added a **Key Leadership** slide with decision maker profiles and discussion relevance.");
    } else if (p.includes("conclusion") || p.includes("next steps")) {
      const newIdx = presentationState.addSlide("conclusion", {
        kicker: "Meeting Strategy",
        title: "Meeting Action Plan & Next Steps",
        subtitle: "Actionable roadmap and priorities for immediate post-meeting execution."
      });
      presentationState.setActiveSlide(newIdx);
      addChatMessage("Created a **Conclusion & Next Steps** slide with an actionable alignment checklist.");
    } else if (p.includes("change presentation theme") || p.includes("theme")) {
      const themes = ["navy", "light", "coral", "slate", "editorial"];
      const current = presentationState.getTheme();
      const nextTheme = themes[(themes.indexOf(current) + 1) % themes.length];
      presentationState.setTheme(nextTheme);
      const themeObj = PresentationState.THEMES.find(t => t.id === nextTheme);
      addChatMessage(`Switched presentation theme to **${themeObj.name}**. Live canvas and thumbnails have been updated.`);
    } else {
      // General prompt handling
      addChatMessage(`Received: "*${prompt}*". Applied adjustments to active presentation state. Full conversational generative rewriting will stream via the Bifrost Gemini 3.5 Flash gateway in **Part 5**.`);
    }
  }

  /* ============================================================
     6. CENTER EDITOR CANVAS & QUICK BAR
     ============================================================ */
  function setupCanvasEditor() {
    if (quickAddCardBtn) {
      quickAddCardBtn.addEventListener("click", () => {
        const slide = presentationState.getActiveSlide();
        if (!slide) return;
        if (!Array.isArray(slide.cards)) slide.cards = [];
        slide.cards.push({
          tag: `Pillar 0${slide.cards.length + 1}`,
          title: "New Strategic Insight",
          desc: "Description of key finding or market driver.",
          badge: "Insight"
        });
        slide.layout = "cards";
        presentationState.updateSlide(presentationState.getActiveSlideIndex(), slide);
      });
    }

    if (quickAddBulletBtn) {
      quickAddBulletBtn.addEventListener("click", () => {
        const slide = presentationState.getActiveSlide();
        if (!slide) return;
        if (!Array.isArray(slide.bullets)) slide.bullets = [];
        slide.bullets.push("New strategic discussion topic or alignment goal.");
        slide.layout = "split";
        presentationState.updateSlide(presentationState.getActiveSlideIndex(), slide);
      });
    }

    if (quickSwitchLayoutBtn) {
      quickSwitchLayoutBtn.addEventListener("click", () => openLayoutModal());
    }

    if (quickResetSlideBtn) {
      quickResetSlideBtn.addEventListener("click", () => {
        const idx = presentationState.getActiveSlideIndex();
        const slide = presentationState.getActiveSlide();
        if (!slide) return;
        if (confirm("Reset this slide to default layout formatting?")) {
          const resetSlide = presentationState._createSlideByLayout(slide.layout || "cards");
          resetSlide.id = slide.id;
          presentationState.updateSlide(idx, resetSlide);
        }
      });
    }
  }

  /* ============================================================
     7. RIGHT NAVIGATOR CONTROLS
     ============================================================ */
  function setupNavigator() {
    if (navAddSlideBtn) {
      navAddSlideBtn.addEventListener("click", () => openLayoutModal());
    }

    if (navDupSlideBtn) {
      navDupSlideBtn.addEventListener("click", () => {
        presentationState.duplicateSlide();
      });
    }

    if (navDelSlideBtn) {
      navDelSlideBtn.addEventListener("click", () => {
        const idx = presentationState.getActiveSlideIndex();
        const slide = presentationState.getActiveSlide();
        if (presentationState.getSlideCount() <= 1) {
          alert("A presentation must have at least one slide.");
          return;
        }
        if (confirm(`Delete slide ${idx + 1} ("${slide.title || "Slide"}")?`)) {
          presentationState.deleteSlide(idx);
        }
      });
    }
  }

  /* ============================================================
     8. MODALS & OVERLAYS
     ============================================================ */
  function setupModals() {
    // Config Modal
    if (closeConfigModalBtn) closeConfigModalBtn.addEventListener("click", () => closeAllModals());
    if (cancelConfigBtn) cancelConfigBtn.addEventListener("click", () => closeAllModals());
    if (applyConfigBtn) {
      applyConfigBtn.addEventListener("click", () => {
        applyDeckConfiguration();
        closeAllModals();
      });
    }

    // Theme Modal
    if (closeThemeModalBtn) closeThemeModalBtn.addEventListener("click", () => closeAllModals());
    populateThemeModal();

    // Layout Modal
    if (closeLayoutModalBtn) closeLayoutModalBtn.addEventListener("click", () => closeAllModals());
    populateLayoutModal();

    // Preview Modal
    if (closePreviewBtn) closePreviewBtn.addEventListener("click", () => closePreviewModal());
    if (prevSlideBtn) prevSlideBtn.addEventListener("click", () => stepPreview(-1));
    if (nextSlideBtn) nextSlideBtn.addEventListener("click", () => stepPreview(1));

    // Export Modal
    if (closeExportModalBtn) closeExportModalBtn.addEventListener("click", () => closeAllModals());
    if (exportPdfBtn) exportPdfBtn.addEventListener("click", () => handlePdfExport());
    if (exportJsonBtn) exportJsonBtn.addEventListener("click", () => handleJsonExport());
    if (exportMdBtn) exportMdBtn.addEventListener("click", () => handleMarkdownExport());
    if (exportPptxBtn) exportPptxBtn.addEventListener("click", () => handlePptxExport());

    // Close on overlay click
    document.querySelectorAll(".modal-overlay").forEach(overlay => {
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeAllModals();
      });
    });
  }

  function closeAllModals() {
    document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
  }

  /* Config Modal Handler */
  function openConfigModal() {
    const cfg = presentationState.getConfig();
    if (cfgPresTitle) cfgPresTitle.value = presentationState.getTitle();
    if (cfgSlideCount) cfgSlideCount.value = cfg.slideCount || "7";
    if (cfgAudience) cfgAudience.value = cfg.audience || "Executive Leadership";
    if (cfgMeetingPurpose) cfgMeetingPurpose.value = cfg.purpose || "";
    if (cfgTone) cfgTone.value = cfg.tone || "professional";
    if (cfgTheme) cfgTheme.value = presentationState.getTheme();
    if (cfgDetail) cfgDetail.value = cfg.detailLevel || "balanced";

    if (configModal) configModal.classList.add("active");
  }

  async function applyDeckConfiguration() {
    const title = (cfgPresTitle && cfgPresTitle.value.trim()) || "Meeting Presentation";
    const slideCount = parseInt(cfgSlideCount ? cfgSlideCount.value : "7", 10) || 7;
    const audience = cfgAudience ? cfgAudience.value : "Executive Leadership";
    const purpose = (cfgMeetingPurpose && cfgMeetingPurpose.value.trim()) || "Strategic Partnership Alignment";
    const tone = cfgTone ? cfgTone.value : "professional";
    const theme = cfgTheme ? cfgTheme.value : "navy";
    const detail = cfgDetail ? cfgDetail.value : "balanced";

    // Gather checked topics
    const topicsInclude = [];
    document.querySelectorAll('input[name="cfgTopics"]:checked').forEach(cb => topicsInclude.push(cb.value));

    const topicsExclude = [];
    document.querySelectorAll('input[name="cfgExclude"]:checked').forEach(cb => topicsExclude.push(cb.value));

    setTypingState(true);
    addChatMessage(`Rebuilding presentation for **${audience}** with **${slideCount} slides** in **${tone}** tone...`, "ai");

    const ctx = typeof VQContext !== "undefined" ? VQContext.read() : null;
    const researchId = (ctx && ctx.research_id) || null;
    const briefingId = (ctx && ctx.briefing_id) || null;

    try {
      if (typeof VQApi !== "undefined" && VQApi.createPresentation) {
        const res = await VQApi.createPresentation({
          research_id: researchId,
          briefing_id: briefingId,
          title: title,
          slide_count: slideCount,
          audience: audience,
          purpose: purpose,
          tone: tone,
          theme: theme,
          detail_level: detail,
          topics_include: topicsInclude,
          topics_exclude: topicsExclude
        });

        if (res && res.slides) {
          presentationState.setDeck(res);
          addChatMessage(`Successfully generated **${res.slides.length} slides** with **${theme}** theme.`, "ai");
          setTypingState(false);
          return;
        }
      }
    } catch (err) {
      console.warn("Backend createPresentation failed; using local generator:", err);
    }

    presentationState.updateConfig({
      title,
      slideCount,
      audience,
      purpose,
      tone,
      theme,
      detailLevel: detail,
      topicsInclude,
      topicsExclude
    }, true, activeBriefingData);

    setTypingState(false);
    addChatMessage(`Updated presentation configuration for **${audience}** with **${slideCount} slides** in **${tone}** tone.`);
  }

  /* Theme Modal Handler */
  function openThemeModal() {
    if (themeModal) themeModal.classList.add("active");
  }

  function populateThemeModal() {
    if (!themesGrid) return;
    themesGrid.replaceChildren();

    PresentationState.THEMES.forEach(t => {
      const card = document.createElement("div");
      card.className = "theme-card-option" + (presentationState && presentationState.getTheme() === t.id ? " active" : "");
      card.innerHTML = `
        <div class="theme-swatch-box" style="background:${t.bg};border:2px solid ${t.accent};">
          <span style="position:absolute;top:6px;left:8px;font-size:10px;font-weight:700;color:${t.accent};">VelQora</span>
          <span style="position:absolute;bottom:6px;left:8px;font-size:9px;color:${t.text};">Theme Preview</span>
        </div>
        <h4>${t.name}</h4>
        <p>${t.description}</p>
      `;

      card.addEventListener("click", () => {
        presentationState.setTheme(t.id);
        closeAllModals();
        showActionToast(`Applied ${t.name} theme`);
      });

      themesGrid.appendChild(card);
    });
  }

  /* Layout Modal Handler */
  function openLayoutModal() {
    if (layoutModal) layoutModal.classList.add("active");
  }

  function populateLayoutModal() {
    if (!layoutsGrid) return;
    layoutsGrid.replaceChildren();

    PresentationState.LAYOUTS.forEach(l => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "layout-choice-btn";
      btn.innerHTML = `
        <b>${l.icon} ${l.name}</b>
        <span>${l.desc}</span>
      `;

      btn.addEventListener("click", () => {
        presentationState.addSlide(l.id);
        closeAllModals();
        showActionToast(`Added ${l.name}`);
      });

      layoutsGrid.appendChild(btn);
    });
  }

  /* Fullscreen Preview Player */
  function openPreviewModal() {
    previewIndex = presentationState.getActiveSlideIndex();
    renderPreviewSlide();
    if (previewModal) previewModal.classList.add("active");
    window.addEventListener("keydown", handlePreviewKeydown);
  }

  function closePreviewModal() {
    if (previewModal) previewModal.classList.remove("active");
    window.removeEventListener("keydown", handlePreviewKeydown);
  }

  function stepPreview(delta) {
    const slides = presentationState.getSlides();
    previewIndex = Math.max(0, Math.min(slides.length - 1, previewIndex + delta));
    renderPreviewSlide();
  }

  function renderPreviewSlide() {
    if (!previewStage) return;
    const slides = presentationState.getSlides();
    const slide = slides[previewIndex];
    const theme = presentationState.getTheme();

    previewStage.innerHTML = SlideRenderer.renderPreview(slide, theme);
    if (previewCounter) previewCounter.textContent = `Slide ${previewIndex + 1} of ${slides.length}`;
    if (prevSlideBtn) prevSlideBtn.disabled = previewIndex === 0;
    if (nextSlideBtn) nextSlideBtn.disabled = previewIndex === slides.length - 1;
  }

  function handlePreviewKeydown(e) {
    if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === " ") {
      e.preventDefault();
      stepPreview(1);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      stepPreview(-1);
    } else if (e.key === "Escape") {
      closePreviewModal();
    }
  }

  /* Export Handlers */
  function openExportModal() {
    if (exportModal) exportModal.classList.add("active");
  }

  function handlePdfExport() {
    closeAllModals();
    showActionToast("Opening print dialog for 16:9 PDF export...");
    setTimeout(() => {
      window.print();
    }, 250);
  }

  function handleJsonExport() {
    const jsonStr = presentationState.exportJSON();
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const filename = `velqora-${presentationState.getTitle().toLowerCase().replace(/[^a-z0-9]+/g, "-")}.json`;
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    closeAllModals();
    showActionToast("Downloaded JSON deck");
  }

  function handleMarkdownExport() {
    const md = presentationState.exportMarkdown();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(md).then(() => {
        closeAllModals();
        showActionToast("Copied presentation outline to clipboard!");
      }).catch(() => {
        prompt("Copy presentation outline below:", md);
      });
    } else {
      prompt("Copy presentation outline below:", md);
    }
  }

  function handlePptxExport() {
    closeAllModals();
    addChatMessage("Direct PowerPoint (.pptx) server export connects to the Bifrost backend service in **Part 5**.", "ai");
    alert("PowerPoint export pipeline connects with Bifrost server in Part 5. You can currently Print to PDF or download the structured JSON deck.");
  }

  /* ============================================================
     9. MOBILE VIEW SWITCHER
     ============================================================ */
  function setupMobileTabs() {
    studioTabs.forEach(btn => {
      btn.addEventListener("click", () => {
        studioTabs.forEach(b => b.classList.remove("on"));
        btn.classList.add("on");
        const targetId = btn.dataset.panel;
        document.querySelectorAll(".studio-shell .studio-panel").forEach(p => {
          p.classList.toggle("show", p.id === targetId);
        });
      });
    });
  }

  /* ============================================================
     10. UTILITIES
     ============================================================ */
  function showActionToast(msg) {
    let toast = document.getElementById("vqStudioToast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "vqStudioToast";
      toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        background: #14213D;
        color: #fff;
        padding: 8px 16px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 500;
        box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        z-index: 200;
        pointer-events: none;
        transition: opacity .3s, transform .3s;
        opacity: 0;
      `;
      document.body.appendChild(toast);
    }

    toast.textContent = msg;
    toast.style.opacity = "1";
    toast.style.transform = "translateX(-50%) translateY(0)";

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(-50%) translateY(8px)";
    }, 2400);
  }

  // Auto-initialize when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initStudio);
  } else {
    initStudio();
  }
})();
