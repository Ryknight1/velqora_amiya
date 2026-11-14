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
  const historyBtn = document.getElementById("historyBtn");
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
  const slideTitleInput = document.getElementById("slideTitleInput");
  const aiRegenSlideBtn = document.getElementById("aiRegenSlideBtn");
  const slideCanvas = document.getElementById("slideCanvas");
  const quickAddCardBtn = document.getElementById("quickAddCardBtn");
  const quickAddBulletBtn = document.getElementById("quickAddBulletBtn");
  const quickSwitchLayoutBtn = document.getElementById("quickSwitchLayoutBtn");
  const quickResetSlideBtn = document.getElementById("quickResetSlideBtn");

  // Advanced Inspector Controls
  const inspectorBar = document.getElementById("inspectorBar");
  const inspectorFieldLabel = document.getElementById("inspectorFieldLabel");
  const elSizeDownBtn = document.getElementById("elSizeDownBtn");
  const elSize = document.getElementById("elSize");
  const elSizeUpBtn = document.getElementById("elSizeUpBtn");
  const elWeight = document.getElementById("elWeight");
  const elAlignLeft = document.getElementById("elAlignLeft");
  const elAlignCenter = document.getElementById("elAlignCenter");
  const elAlignRight = document.getElementById("elAlignRight");
  const elColor = document.getElementById("elColor");
  const elBg = document.getElementById("elBg");
  const elPosX = document.getElementById("elPosX");
  const elPosY = document.getElementById("elPosY");
  const elWidth = document.getElementById("elWidth");
  const elHeight = document.getElementById("elHeight");
  const addTextBtn = document.getElementById("addTextBtn");
  const addShapeBtn = document.getElementById("addShapeBtn");
  const delElBtn = document.getElementById("delElBtn");

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
  const genPptxBtn = document.getElementById("genPptxBtn");
  const downloadPptxBtn = document.getElementById("downloadPptxBtn");
  const exportStatusBanner = document.getElementById("exportStatusBanner");
  const exportSpinner = document.getElementById("exportSpinner");
  const exportStatusText = document.getElementById("exportStatusText");
  const pptxExportDetails = document.getElementById("pptxExportDetails");

  // Rename Modal & Header Display
  const presTitleDisplay = document.getElementById("presTitleDisplay");
  const renamePresBtn = document.getElementById("renamePresBtn");
  const renameModal = document.getElementById("renameModal");
  const closeRenameModalBtn = document.getElementById("closeRenameModalBtn");
  const cancelRenameBtn = document.getElementById("cancelRenameBtn");
  const applyRenameBtn = document.getElementById("applyRenameBtn");
  const renamePresInput = document.getElementById("renamePresInput");

  // Version History Modal
  const historyModal = document.getElementById("historyModal");
  const closeHistoryModalBtn = document.getElementById("closeHistoryModalBtn");
  const versionList = document.getElementById("versionList");
  const snapshotSummaryInput = document.getElementById("snapshotSummaryInput");
  const createSnapshotBtn = document.getElementById("createSnapshotBtn");

  // Mobile Tabs
  const studioTabs = document.querySelectorAll(".studio-tabs button");

  // State instances
  let presentationState = null;
  let activeBriefingData = null;
  let previewIndex = 0;
  let lastPromptExecuted = null;
  let lastExportDownloadUrl = null;
  let inlineEditDebounce = null;
  let draggedSlideIndex = null;
  let autosaveTimer = null;
  let isSaving = false;

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
    let hasLoaded = presId ? presentationState.loadFromStorage(`vq_pres_${presId}`) : presentationState.loadFromStorage();

    // If presId is provided and local draft not found, fetch from backend API
    if (!hasLoaded && presId && typeof VQApi !== "undefined") {
      try {
        const presRes = await VQApi.getPresentation(presId);
        if (presRes) {
          presentationState.loadFromDeck(presRes);
          hasLoaded = true;
        }
      } catch (err) {
        console.warn("Could not fetch remote presentation from backend:", err);
      }
    }

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
    setupInspectorListeners();
    setupVersionHistory();
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
    syncInspector();
  }

  function updateHeaderStatus(status) {
    if (!savedBadge) return;
    savedBadge.classList.remove("saving", "failed");

    if (status === "saving") {
      savedBadge.classList.add("saving");
      savedBadge.textContent = "Saving...";
      savedBadge.style.opacity = "1";
      if (dirtyFlag) dirtyFlag.hidden = true;
    } else if (status === "failed") {
      savedBadge.classList.add("failed");
      savedBadge.textContent = "⚠ Save failed";
      savedBadge.style.opacity = "1";
      if (dirtyFlag) dirtyFlag.hidden = false;
    } else if (status === "saved") {
      savedBadge.style.opacity = "1";
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      savedBadge.textContent = `✓ Saved at ${timeStr}`;
      if (dirtyFlag) dirtyFlag.hidden = true;
    } else {
      if (dirtyFlag) dirtyFlag.hidden = !presentationState.isDirty;
      if (presentationState.isDirty) {
        savedBadge.style.opacity = "0.3";
      } else {
        savedBadge.style.opacity = "1";
        savedBadge.textContent = presentationState.lastSavedAt
          ? `✓ Saved at ${presentationState.lastSavedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
          : "✓ Saved";
      }
    }
  }

  function scheduleAutosave() {
    clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => {
      if (presentationState && presentationState.isDirty && !isSaving) {
        saveToBackend(true);
      }
    }, 2000);
  }

  async function saveToBackend(isAutosave = false, summary = null) {
    if (!presentationState || isSaving) return;
    const deck = presentationState.getDeck();
    if (!deck) return;

    isSaving = true;
    updateHeaderStatus("saving");
    if (saveBtn) saveBtn.disabled = true;

    try {
      const presId = deck.id || deck.presentation_id;
      if (typeof VQApi !== "undefined" && VQApi.updatePresentation && presId) {
        await VQApi.updatePresentation(presId, deck, summary, !isAutosave);
      }
      presentationState.saveToStorage();
      updateHeaderStatus("saved");
      if (!isAutosave) {
        showActionToast("Presentation saved successfully");
      }
    } catch (err) {
      console.warn("Save failed; preserving state locally:", err);
      presentationState.saveToStorage();
      updateHeaderStatus("failed");
      if (!isAutosave) {
        showActionToast("Saved locally (offline mode)");
      }
    } finally {
      isSaving = false;
      if (saveBtn) saveBtn.disabled = false;
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
    if (presTitleDisplay) {
      presTitleDisplay.textContent = presentationState.getTitle() || "Meeting Presentation";
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
        syncInspector();
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
      syncInspector();
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
    scheduleAutosave();
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
    syncInspector();
  }

  function onSlideChange() {
    renderActiveSlide();
    updateSlideLabels();
    syncInspector();

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

    // History
    if (historyBtn) {
      historyBtn.addEventListener("click", () => openHistoryModal());
    }

    // Save
    if (saveBtn) {
      saveBtn.addEventListener("click", () => {
        saveToBackend(false, "Manual user save");
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
        saveToBackend(false, "Keyboard shortcut save");
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

  let isPromptRunning = false;

  async function executePrompt(promptText) {
    if (isPromptRunning) return;
    isPromptRunning = true;
    lastPromptExecuted = promptText;
    addChatMessage(promptText, "user");
    setTypingState(true);
    const sendBtn = document.getElementById("sendBtn");
    if (sendBtn) sendBtn.disabled = true;
    if (chatInput) chatInput.disabled = true;

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
          addChatMessage(`Generated a complete **${res.slides.length}-slide presentation** grounded in verified research intelligence.`, "ai");
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
          return;
        }
      }
    } catch (err) {
      console.warn("AI backend call encountered an error; falling back gracefully:", err);
      // Graceful local handling to prevent UI disruption if Bifrost gateway is unreachable
      processAgentAction(promptText);
      addChatMessage("*(AI assistant service temporarily unreachable; applied local update)*", "ai");
      return;
    } finally {
      isPromptRunning = false;
      setTypingState(false);
      if (sendBtn) sendBtn.disabled = false;
      if (chatInput) {
        chatInput.disabled = false;
        chatInput.focus();
      }
    }

    // Default local fallback if no VQApi
    processAgentAction(promptText);
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
      addChatMessage(`Welcome to Presentation Studio. Loaded research briefing for **${entityName}** with verified source citations. You can edit slides directly, adjust layouts, or ask for adjustments.`);
    } else {
      addChatMessage(`Welcome to Presentation Studio. Workspace initialized with meeting presentation templates for **${entityName}**. Customize slides inline or use the prompts below.`);
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
      presentationState.setTheme("corporate_blue");
      const cfg = presentationState.getConfig();
      cfg.tone = "professional";
      presentationState.updateConfig(cfg, false);
      addChatMessage("Updated presentation theme to **Corporate Blue** with high-contrast executive styling.");
    } else if (p.includes("two-column") || p.includes("two column")) {
      const slide = presentationState.getActiveSlide();
      if (slide) {
        slide.layout = "split";
        if (!slide.bullets || !slide.bullets.length) {
          slide.bullets = [
            "Established enterprise market presence and customer adoption.",
            "Active discussions with commercial and technical stakeholders.",
            "Clear technical differentiation in core product capabilities."
          ];
        }
        slide.highlightTitle = "Strategic Value";
        slide.highlightBody = "Strong strategic fit with clear mutual collaboration opportunities.";
        presentationState.updateSlide(presentationState.getActiveSlideIndex(), slide);
      }
      addChatMessage("Switched slide layout to **Two-Column** with strategic bullets and highlighted takeaway.");
    } else if (p.includes("heading bigger") || p.includes("bigger heading") || p.includes("larger heading")) {
      const idx = presentationState.getActiveSlideIndex();
      presentationState.updateElementStyle(idx, "title", { fontSize: "36px", fontWeight: "700" });
      addChatMessage("Updated title size to **36px**.");
    } else if (p.includes("dark blue") || p.includes("corporate blue")) {
      presentationState.setTheme("corporate_blue");
      addChatMessage("Changed presentation theme to **Corporate Blue** (Royal Blue & Midnight Navy).");
    } else if (p.includes("consistent") || p.includes("make all slides consistent")) {
      const slides = presentationState.getSlides();
      const entity = activeBriefingData && activeBriefingData.entity ? activeBriefingData.entity.name : "VelQora";
      slides.forEach(s => {
        s.footer = `${entity} • VelQora Grounded Intelligence`;
      });
      presentationState.isDirty = true;
      renderAll();
      addChatMessage("Applied consistent footers and source references across all slides.");
    } else if (p.includes("less crowded") || p.includes("less dense")) {
      const slide = presentationState.getActiveSlide();
      if (slide) {
        if (Array.isArray(slide.cards) && slide.cards.length > 3) slide.cards = slide.cards.slice(0, 3);
        if (Array.isArray(slide.bullets) && slide.bullets.length > 3) slide.bullets = slide.bullets.slice(0, 3);
        if (slide.subtitle && slide.subtitle.length > 100) slide.subtitle = slide.subtitle.slice(0, 97) + "...";
        presentationState.updateSlide(presentationState.getActiveSlideIndex(), slide);
      }
      addChatMessage("Reduced text density and adjusted spacing for readability.");
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
      addChatMessage("Updated **Slide 3** with a clearer narrative focus and verified milestone data.");
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
      addChatMessage(`Applied requested adjustments for: "*${prompt}*". You can refine text inline or reorder slides in the navigator.`);
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
     6B. ADVANCED INSPECTOR DOCK & MANUAL CONTROLS
     ============================================================ */
  function syncInspector() {
    const slide = presentationState ? presentationState.getActiveSlide() : null;
    const selField = presentationState ? presentationState.getSelectedElement() : null;

    if (slideTitleInput && slide) {
      slideTitleInput.value = slide.title || "";
    }

    if (!selField) {
      if (inspectorFieldLabel) inspectorFieldLabel.textContent = "Selection: None";
      if (delElBtn) delElBtn.disabled = true;
      return;
    }

    if (delElBtn) delElBtn.disabled = false;
    if (inspectorFieldLabel) {
      const displayLabel = selField.replace(/^custom_/, "Custom ").replace(/_/g, " ");
      inspectorFieldLabel.textContent = `Selected: ${displayLabel}`;
    }

    // Check if custom element
    const customEl = slide && Array.isArray(slide.customElements)
      ? slide.customElements.find(e => e.id === selField)
      : null;

    if (customEl) {
      if (elSize) elSize.value = customEl.fontSize || "16px";
      if (elWeight) elWeight.value = customEl.fontWeight || "400";
      if (elColor && customEl.color && customEl.color.startsWith("#")) elColor.value = customEl.color;
      if (elBg && customEl.bg && customEl.bg.startsWith("#")) elBg.value = customEl.bg;
      if (elPosX) elPosX.value = customEl.x !== undefined ? customEl.x : 10;
      if (elPosY) elPosY.value = customEl.y !== undefined ? customEl.y : 40;
      if (elWidth) elWidth.value = customEl.w !== undefined ? customEl.w : 30;
      if (elHeight) elHeight.value = customEl.h !== undefined ? customEl.h : 15;
    } else {
      const st = (slide && slide.elementStyles && slide.elementStyles[selField]) || {};
      const pos = (slide && slide.elementPositions && slide.elementPositions[selField]) || {};

      if (elSize) elSize.value = st.fontSize || "16px";
      if (elWeight) elWeight.value = st.fontWeight || "400";
      if (elColor && st.color && st.color.startsWith("#")) elColor.value = st.color;
      if (elBg && st.bg && st.bg.startsWith("#")) elBg.value = st.bg;
      if (elPosX) elPosX.value = pos.x !== undefined ? pos.x : "";
      if (elPosY) elPosY.value = pos.y !== undefined ? pos.y : "";
      if (elWidth) elWidth.value = pos.w !== undefined ? pos.w : "";
      if (elHeight) elHeight.value = pos.h !== undefined ? pos.h : "";
    }
  }

  function setupInspectorListeners() {
    if (slideTitleInput) {
      slideTitleInput.addEventListener("input", () => {
        const val = slideTitleInput.value.trim();
        presentationState.changeSlideTitle(presentationState.getActiveSlideIndex(), val);
        scheduleAutosave();
      });
    }

    if (aiRegenSlideBtn) {
      aiRegenSlideBtn.addEventListener("click", () => {
        const idx = presentationState.getActiveSlideIndex();
        executePrompt(`Improve and regenerate slide ${idx + 1} with deep business intelligence.`);
      });
    }

    if (elSizeDownBtn) {
      elSizeDownBtn.addEventListener("click", () => {
        const cur = parseInt(elSize.value, 10) || 16;
        const next = Math.max(10, cur - 2) + "px";
        elSize.value = next;
        applyStyleToSelected({ fontSize: next });
      });
    }

    if (elSizeUpBtn) {
      elSizeUpBtn.addEventListener("click", () => {
        const cur = parseInt(elSize.value, 10) || 16;
        const next = Math.min(64, cur + 2) + "px";
        elSize.value = next;
        applyStyleToSelected({ fontSize: next });
      });
    }

    if (elSize) {
      elSize.addEventListener("change", () => {
        let val = elSize.value.trim();
        if (!val.endsWith("px")) val += "px";
        applyStyleToSelected({ fontSize: val });
      });
    }

    if (elWeight) {
      elWeight.addEventListener("change", () => {
        applyStyleToSelected({ fontWeight: elWeight.value });
      });
    }

    if (elAlignLeft) {
      elAlignLeft.addEventListener("click", () => applyStyleToSelected({ align: "left" }));
    }
    if (elAlignCenter) {
      elAlignCenter.addEventListener("click", () => applyStyleToSelected({ align: "center" }));
    }
    if (elAlignRight) {
      elAlignRight.addEventListener("click", () => applyStyleToSelected({ align: "right" }));
    }

    if (elColor) {
      elColor.addEventListener("input", () => {
        applyStyleToSelected({ color: elColor.value });
      });
    }

    if (elBg) {
      elBg.addEventListener("input", () => {
        applyStyleToSelected({ bg: elBg.value });
      });
    }

    [elPosX, elPosY, elWidth, elHeight].forEach(inp => {
      if (inp) {
        inp.addEventListener("change", () => {
          applyPositionToSelected({
            x: elPosX.value !== "" ? parseFloat(elPosX.value) : undefined,
            y: elPosY.value !== "" ? parseFloat(elPosY.value) : undefined,
            w: elWidth.value !== "" ? parseFloat(elWidth.value) : undefined,
            h: elHeight.value !== "" ? parseFloat(elHeight.value) : undefined,
          });
        });
      }
    });

    if (addTextBtn) {
      addTextBtn.addEventListener("click", () => {
        const activeIdx = presentationState.getActiveSlideIndex();
        presentationState.addElement(activeIdx, {
          type: "text",
          content: "Strategic Insight Note",
          x: 15,
          y: 45,
          w: 40,
          h: 15,
          fontSize: "14px",
          fontWeight: "500"
        });
        showActionToast("Added floating text element");
        syncInspector();
        scheduleAutosave();
      });
    }

    if (addShapeBtn) {
      addShapeBtn.addEventListener("click", () => {
        const activeIdx = presentationState.getActiveSlideIndex();
        presentationState.addElement(activeIdx, {
          type: "shape",
          content: "Key Alignment Area",
          x: 20,
          y: 50,
          w: 35,
          h: 18,
          bg: "var(--slide-card-bg)",
          fontSize: "13px",
          fontWeight: "600"
        });
        showActionToast("Added card shape element");
        syncInspector();
        scheduleAutosave();
      });
    }

    if (delElBtn) {
      delElBtn.addEventListener("click", () => {
        const selField = presentationState.getSelectedElement();
        if (!selField) return;
        const activeIdx = presentationState.getActiveSlideIndex();
        if (presentationState.deleteElement(activeIdx, selField)) {
          showActionToast(`Deleted ${selField}`);
          syncInspector();
          scheduleAutosave();
        }
      });
    }
  }

  function applyStyleToSelected(stylePatch) {
    const selField = presentationState.getSelectedElement();
    if (!selField) return;
    const activeIdx = presentationState.getActiveSlideIndex();
    const slide = presentationState.getActiveSlide();

    if (slide && Array.isArray(slide.customElements)) {
      const customEl = slide.customElements.find(e => e.id === selField);
      if (customEl) {
        Object.assign(customEl, stylePatch);
        presentationState.isDirty = true;
        renderActiveSlide();
        scheduleAutosave();
        return;
      }
    }

    presentationState.updateElementStyle(activeIdx, selField, stylePatch);
    scheduleAutosave();
  }

  function applyPositionToSelected(posPatch) {
    const selField = presentationState.getSelectedElement();
    if (!selField) return;
    const activeIdx = presentationState.getActiveSlideIndex();
    const slide = presentationState.getActiveSlide();

    if (slide && Array.isArray(slide.customElements)) {
      const customEl = slide.customElements.find(e => e.id === selField);
      if (customEl) {
        if (posPatch.x !== undefined) customEl.x = posPatch.x;
        if (posPatch.y !== undefined) customEl.y = posPatch.y;
        if (posPatch.w !== undefined) customEl.w = posPatch.w;
        if (posPatch.h !== undefined) customEl.h = posPatch.h;
        presentationState.isDirty = true;
        renderActiveSlide();
        scheduleAutosave();
        return;
      }
    }

    presentationState.updateElementPosition(activeIdx, selField, posPatch);
    scheduleAutosave();
  }

  /* ============================================================
     6C. VERSION HISTORY WORKFLOW
     ============================================================ */
  function setupVersionHistory() {
    if (historyBtn) {
      historyBtn.addEventListener("click", () => openHistoryModal());
    }
    if (closeHistoryModalBtn) {
      closeHistoryModalBtn.addEventListener("click", () => closeAllModals());
    }
    if (createSnapshotBtn) {
      createSnapshotBtn.addEventListener("click", async () => {
        const summary = (snapshotSummaryInput && snapshotSummaryInput.value.trim()) || "Manual version snapshot";
        if (snapshotSummaryInput) snapshotSummaryInput.value = "";
        await saveToBackend(false, summary);
        await loadVersionsList();
      });
    }
  }

  async function openHistoryModal() {
    if (historyModal) historyModal.classList.add("active");
    await loadVersionsList();
  }

  async function loadVersionsList() {
    if (!versionList) return;
    versionList.innerHTML = `<p style="font-size:12px;color:var(--ink-40);text-align:center;padding:16px;">Loading versions...</p>`;

    const deck = presentationState.getDeck();
    const presId = deck ? (deck.id || deck.presentation_id) : null;
    if (!presId || typeof VQApi === "undefined" || !VQApi.getPresentationVersions) {
      versionList.innerHTML = `<p style="font-size:12px;color:var(--ink-40);text-align:center;padding:16px;">Version history connects when presentations are persisted to the backend.</p>`;
      return;
    }

    try {
      const res = await VQApi.getPresentationVersions(presId);
      if (!res || !res.versions || !res.versions.length) {
        versionList.innerHTML = `<p style="font-size:12px;color:var(--ink-40);text-align:center;padding:16px;">No saved snapshots yet. Click "+ Save Snapshot" to create one.</p>`;
        return;
      }

      versionList.replaceChildren();
      const versionsReversed = res.versions.slice().reverse();
      versionsReversed.forEach(v => {
        const item = document.createElement("div");
        item.className = "version-item";
        const dateStr = v.timestamp ? new Date(v.timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : "Recent";

        item.innerHTML = `
          <div class="version-info">
            <span class="version-title">Version ${v.version}: ${SlideRenderer.esc(v.summary || "Snapshot")}</span>
            <span class="version-meta">${dateStr} • ${v.slide_count || 0} slides</span>
          </div>
          <button type="button" class="version-restore-btn" data-version="${v.version}">Restore</button>
        `;

        const restoreBtn = item.querySelector(".version-restore-btn");
        restoreBtn.addEventListener("click", async () => {
          if (confirm(`Restore Version ${v.version} ("${v.summary}")? Current work will be auto-saved first.`)) {
            try {
              const restored = await VQApi.restorePresentationVersion(presId, v.version);
              if (restored) {
                presentationState.setDeck(restored);
                closeAllModals();
                showActionToast(`Restored Version ${v.version}`);
                addChatMessage(`Restored presentation to **Version ${v.version}** (${v.summary}). Previous state was auto-saved as a backup.`, "ai");
              }
            } catch (err) {
              alert("Failed to restore version: " + (err.message || "Unknown error"));
            }
          }
        });

        versionList.appendChild(item);
      });
    } catch (err) {
      versionList.innerHTML = `<p style="font-size:12px;color:var(--warn);text-align:center;padding:16px;">Could not load versions: ${SlideRenderer.esc(err.message || "Network error")}</p>`;
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
    if (genPptxBtn) genPptxBtn.addEventListener("click", () => handlePptxExport());
    if (downloadPptxBtn) downloadPptxBtn.addEventListener("click", () => handleDownloadPptx());

    // Rename Modal
    if (renamePresBtn) renamePresBtn.addEventListener("click", () => openRenameModal());
    if (closeRenameModalBtn) closeRenameModalBtn.addEventListener("click", () => closeAllModals());
    if (cancelRenameBtn) cancelRenameBtn.addEventListener("click", () => closeAllModals());
    if (applyRenameBtn) applyRenameBtn.addEventListener("click", () => handleApplyRename());
    if (renamePresInput) {
      renamePresInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          handleApplyRename();
        }
      });
    }

    // Close on overlay click
    document.querySelectorAll(".modal-overlay").forEach(overlay => {
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeAllModals();
      });
    });

    // Close on Escape key press
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeAllModals();
      }
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

  async function handlePptxExport() {
    if (!presentationState) return;
    const presId = presentationState.getId();
    if (!presId) {
      showActionToast("Please save the presentation before exporting.");
      return;
    }

    if (exportStatusBanner) {
      exportStatusBanner.style.display = "flex";
      exportStatusBanner.className = "export-status-banner loading";
    }
    if (exportSpinner) {
      exportSpinner.style.display = "inline-block";
    }
    if (exportStatusText) {
      exportStatusText.textContent = "Generating 16:9 PowerPoint presentation...";
    }
    if (genPptxBtn) {
      genPptxBtn.disabled = true;
      genPptxBtn.textContent = "Generating...";
    }
    if (exportPptxBtn) {
      exportPptxBtn.disabled = true;
      exportPptxBtn.textContent = "Generating...";
    }
    if (downloadPptxBtn) {
      downloadPptxBtn.style.display = "none";
    }

    try {
      // 1. Ensure any pending edits are saved to the backend
      await saveToBackend(false, "Pre-export auto-save");

      // 2. Call backend export endpoint
      const res = await VQApi.exportPresentation(presId, "pptx");
      lastExportDownloadUrl = res.download_url;

      if (exportStatusBanner) {
        exportStatusBanner.className = "export-status-banner success";
      }
      if (exportSpinner) {
        exportSpinner.style.display = "none";
      }
      const sizeKb = Math.round((res.file_size_bytes || 0) / 1024);
      if (exportStatusText) {
        exportStatusText.textContent = `✓ PowerPoint deck ready! (${res.file_name} • ${sizeKb} KB)`;
      }
      if (pptxExportDetails) {
        pptxExportDetails.style.display = "block";
        pptxExportDetails.textContent = `Generated: ${new Date(res.created_at || Date.now()).toLocaleTimeString()} • 16:9 Widescreen • Editable Shapes & Text`;
      }

      if (downloadPptxBtn) {
        downloadPptxBtn.style.display = "inline-flex";
        downloadPptxBtn.textContent = `⬇ Download ${res.file_name}`;
      }

      showActionToast("PowerPoint deck generated successfully!");
      addChatMessage(`PowerPoint file **${res.file_name}** is ready. Download it directly below or access it from the Export dialog.`, "ai");

      // Automatically trigger file download for convenience
      const a = document.createElement("a");
      a.href = res.download_url;
      a.download = res.file_name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

    } catch (err) {
      console.error("PowerPoint export failed:", err);
      if (exportStatusBanner) {
        exportStatusBanner.className = "export-status-banner error";
      }
      if (exportSpinner) {
        exportSpinner.style.display = "none";
      }
      if (exportStatusText) {
        exportStatusText.textContent = `Export failed: ${err.message || "Could not generate PPTX."}`;
      }
      showActionToast(`Export error: ${err.message || "Failed"}`);
    } finally {
      if (genPptxBtn) {
        genPptxBtn.disabled = false;
        genPptxBtn.textContent = "Generate PowerPoint";
      }
      if (exportPptxBtn) {
        exportPptxBtn.disabled = false;
        exportPptxBtn.textContent = "Generate PowerPoint";
      }
    }
  }

  function handleDownloadPptx() {
    if (!lastExportDownloadUrl && presentationState) {
      lastExportDownloadUrl = VQApi.getPresentationDownloadUrl(presentationState.getId());
    }
    if (lastExportDownloadUrl) {
      const a = document.createElement("a");
      a.href = lastExportDownloadUrl;
      const cleanTitle = (presentationState.getTitle() || "Presentation").replace(/[^a-zA-Z0-9_\- ]/g, "").trim().replace(/\s+/g, "_");
      a.download = `${cleanTitle || "VelQora_Presentation"}.pptx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      showActionToast("Downloading PowerPoint deck...");
    } else {
      handlePptxExport();
    }
  }

  function openRenameModal() {
    if (!presentationState) return;
    if (renamePresInput) {
      renamePresInput.value = presentationState.getTitle() || "";
    }
    if (renameModal) {
      renameModal.classList.add("active");
      setTimeout(() => {
        if (renamePresInput) {
          renamePresInput.focus();
          renamePresInput.select();
        }
      }, 50);
    }
  }

  function handleApplyRename() {
    if (!presentationState) return;
    const newTitle = (renamePresInput ? renamePresInput.value : "").trim();
    if (!newTitle) {
      showActionToast("Please enter a presentation title.");
      return;
    }
    presentationState.setTitle(newTitle);
    if (presTitleDisplay) {
      presTitleDisplay.textContent = newTitle;
    }
    closeAllModals();
    saveToBackend(false, `Renamed presentation to ${newTitle}`);
    showActionToast("Presentation renamed");
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
