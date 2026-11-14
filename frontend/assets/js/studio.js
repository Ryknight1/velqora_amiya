/* Presentation Studio foundation — tabs, context loading, theme selection, and canvas scaffolding */
(function(){
  const chatLog = document.getElementById("chatLog");
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const promptRow = document.getElementById("promptRow");
  const themePick = document.getElementById("themePick");
  const presTitle = document.getElementById("presTitle");
  const slideCanvas = document.getElementById("slideCanvas");
  const thumbList = document.getElementById("thumbList");
  const slideCountLabel = document.getElementById("slideCountLabel");
  const dirtyFlag = document.getElementById("dirtyFlag");

  const THEMES = [
    {id: "navy", name: "Executive Navy"},
    {id: "light", name: "Clean Minimalist"},
    {id: "coral", name: "VelQora Coral"},
    {id: "dark", name: "Modern Dark"}
  ];

  const PROMPTS = [
    "7-slide executive briefing",
    "Focus on recent developments",
    "Highlight key people & leadership",
    "Lead with strategic talking points"
  ];

  // Initialize theme dropdown
  if (themePick && !themePick.children.length) {
    THEMES.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      themePick.appendChild(opt);
    });
  }

  // Initialize quick prompt chips
  if (promptRow && !promptRow.children.length) {
    PROMPTS.forEach(text => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = text;
      btn.addEventListener("click", () => {
        if (chatInput) {
          chatInput.value = text;
          chatInput.focus();
        }
      });
      promptRow.appendChild(btn);
    });
  }

  // Append a message to the chat log
  function addMessage(text, kind = "ai") {
    if (!chatLog) return;
    const div = document.createElement("div");
    div.className = "msg " + (kind === "user" ? "user" : (kind === "err" ? "err" : "ai"));
    div.innerHTML = typeof text === "string" ? esc(text).replace(/\n/g, "<br>") : "";
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  // Tab switching for responsive layouts
  const tabBtns = document.querySelectorAll(".studio-tabs button");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("on"));
      btn.classList.add("on");
      const target = btn.dataset.panel;
      document.querySelectorAll(".studio-shell .studio-panel").forEach(p => {
        p.classList.toggle("show", p.id === target);
      });
    });
  });

  // Render a placeholder slide on the canvas
  function renderPlaceholderSlide(title, subtitle) {
    if (!slideCanvas) return;
    slideCanvas.innerHTML = `
      <div style="height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:40px;text-align:center;background:linear-gradient(145deg,#14213d,#101a30);color:#faf6ef;">
        <span style="font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#ff5858;margin-bottom:12px;">Executive Briefing</span>
        <h2 style="font-family:var(--serif);font-size:clamp(22px,3vw,34px);font-weight:500;margin-bottom:12px;color:#fff;">${esc(title || "Meeting Presentation")}</h2>
        <p style="font-size:15px;color:rgba(250,246,239,.75);max-width:540px;">${esc(subtitle || "VelQora presentation studio workspace. Ready for slide generation.")}</p>
      </div>`;
  }

  // Populate thumbnails
  function renderThumbnails(count = 7) {
    if (!thumbList) return;
    thumbList.replaceChildren();
    if (slideCountLabel) slideCountLabel.textContent = `(${count})`;
    for (let i = 1; i <= count; i++) {
      const d = document.createElement("div");
      d.className = "thumb" + (i === 1 ? " on" : "");
      d.innerHTML = `
        <div class="mini" style="background:#14213d;display:flex;align-items:center;justify-content:center;color:#ff5858;font-size:10px;font-weight:700;">${i}</div>
        <small>${i === 1 ? "Title Slide" : "Slide " + i}</small>`;
      d.addEventListener("click", () => {
        thumbList.querySelectorAll(".thumb").forEach(t => t.classList.remove("on"));
        d.classList.add("on");
        const lbl = document.getElementById("slideLabel");
        if (lbl) lbl.textContent = `Slide ${i} of ${count}`;
      });
      thumbList.appendChild(d);
    }
  }

  // Read workflow context
  const ctx = typeof VQContext !== "undefined" ? VQContext.fromLocation() : null;
  const entityName = (ctx && ctx.entity_name) || "";
  if (presTitle) {
    presTitle.value = entityName ? `${entityName} — Strategic Briefing` : "Executive Meeting Presentation";
  }

  renderPlaceholderSlide(presTitle ? presTitle.value : "", entityName ? `Prepared with research context for ${entityName}` : "");
  renderThumbnails(7);

  if (entityName) {
    addMessage(`Welcome to Presentation Studio. Research context is loaded for **${entityName}**. You can customize your slide settings and generate slides when ready.`);
  } else {
    addMessage("Welcome to Presentation Studio. You can design presentations from scratch or run research first to auto-populate briefing facts.");
  }

  // Handle chat submission
  if (chatForm && chatInput) {
    chatForm.addEventListener("submit", e => {
      e.preventDefault();
      const val = chatInput.value.trim();
      if (!val) return;
      addMessage(val, "user");
      chatInput.value = "";
      setTimeout(() => {
        addMessage(`VelQora received: "${val}". Slide generation and live editing will be active in the next stage.`);
      }, 400);
    });
  }

  // Action button handlers
  const saveBtn = document.getElementById("saveBtn");
  if (saveBtn) {
    saveBtn.addEventListener("click", () => {
      if (dirtyFlag) dirtyFlag.hidden = true;
      addMessage("Presentation draft saved to local workspace.");
    });
  }
})();
