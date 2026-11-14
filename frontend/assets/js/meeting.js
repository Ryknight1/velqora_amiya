/* VelQora Meeting Preparation Workspace Controller */
(function(){
  const meetRoot = document.getElementById("meetRoot");
  const backIntel = document.getElementById("backIntel");
  const toStudio = document.getElementById("toStudio");

  if (!meetRoot) return;

  const CHECKLIST_ITEMS = [
    "Review company overview and verified background",
    "Verify key facts and citations for claims you plan to cite",
    "Review executive leadership profiles and recent moves",
    "Prioritize 3 primary meeting talking points",
    "Prepare responses for potential risks and open questions",
    "Rehearse opening 60 seconds of the conversation",
    "Generate and review the meeting presentation slides"
  ];

  function renderList(items, emptyText = "Not available from retrieved sources.") {
    if (!items || !items.length) {
      return `<p class="muted">${esc(emptyText)}</p>`;
    }
    return `<ul>${items.map(i => {
      const text = typeof i === "string" ? i : (i.text || "");
      return `<li>${esc(text)}<span class="kind-ai">AI analysis</span></li>`;
    }).join("")}</ul>`;
  }

  function generateStrategy(b) {
    const entityName = (b.entity && b.entity.name) || "this organization";
    const purpose = (b.meeting && b.meeting.purpose) || "the upcoming discussion";
    const topPoints = (b.meeting_talking_points || []).slice(0, 2).map(p => p.text).filter(Boolean);
    const topRisk = (b.potential_risks || [])[0];

    const strategyParts = [
      `Walk into the meeting ready to address ${entityName} focused around ${purpose}.`
    ];
    if (topPoints.length) {
      strategyParts.push(`Lead the conversation with: "${topPoints[0]}"`);
    }
    if (topRisk) {
      strategyParts.push(`Stay mindful of: "${topRisk.text}"`);
    }
    if (!b.ai || !b.ai.analysis_available) {
      strategyParts.push("Note: AI analysis was unavailable for this briefing — stick to verified source facts.");
    }
    return strategyParts.join(" ");
  }

  function renderPreparation(b) {
    const briefingId = b.briefing_id || "default";
    const storageKey = `vq_check_${briefingId}`;
    let savedChecks = {};
    try {
      savedChecks = JSON.parse(localStorage.getItem(storageKey) || "{}");
    } catch (_) {}

    const totalChecks = CHECKLIST_ITEMS.length;
    let checkedCount = CHECKLIST_ITEMS.filter((_, idx) => !!savedChecks[idx]).length;

    const entityName = (b.entity && b.entity.name) || "Meeting Target";
    const meetingTime = (b.meeting && b.meeting.time) || "Date / time not set";
    const meetingPurpose = (b.meeting && b.meeting.purpose) || "General discussion";
    const overview = b.overview || "No verified overview available.";

    const checklistHtml = CHECKLIST_ITEMS.map((item, idx) => {
      const isChecked = !!savedChecks[idx];
      return `
        <li class="check-item ${isChecked ? "completed" : ""}" data-idx="${idx}">
          <input type="checkbox" id="chk_${idx}" ${isChecked ? "checked" : ""}>
          <label for="chk_${idx}">${esc(item)}</label>
        </li>`;
    }).join("");

    meetRoot.innerHTML = `
      <div class="meet-grid">
        <div class="meet-col">
          <!-- Meeting Overview -->
          <article class="meet-card">
            <h2>Meeting Overview</h2>
            <div>
              <h3 style="font-size:18px;font-weight:600;color:var(--deep);">${esc(entityName)}</h3>
              <div class="meet-meta-tags">
                <span class="meet-pill highlight">📅 ${esc(meetingTime)}</span>
                <span class="meet-pill">🎯 ${esc(meetingPurpose)}</span>
              </div>
            </div>
            <div style="margin-top:6px;">
              <strong style="font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink-60);">Research Summary:</strong>
              <p style="font-size:14px;line-height:1.6;color:var(--navy);margin-top:4px;">${esc(overview)}</p>
            </div>
          </article>

          <!-- Meeting Strategy -->
          <article class="meet-card strategy-card">
            <h2>
              Meeting Strategy
              <span class="kind-ai">AI Strategy</span>
            </h2>
            <div class="strategy-callout">
              ${esc(generateStrategy(b))}
            </div>
          </article>

          <!-- Talking Points -->
          <article class="meet-card">
            <h2>Meeting Talking Points</h2>
            ${renderList(b.meeting_talking_points, "No strategic talking points identified.")}
          </article>

          <!-- Suggested Questions -->
          <article class="meet-card">
            <h2>Suggested Questions</h2>
            ${renderList(b.suggested_questions, "No suggested questions generated.")}
          </article>

          <!-- Potential Risks -->
          <article class="meet-card">
            <h2>Potential Risks</h2>
            ${renderList(b.potential_risks, "No specific discussion risks identified from sources.")}
          </article>

          <!-- Opportunities -->
          <article class="meet-card">
            <h2>Opportunities</h2>
            ${renderList(b.opportunities, "No specific opportunities identified.")}
          </article>
        </div>

        <aside class="meet-col checklist-sidebar">
          <article class="meet-card">
            <h2>
              Preparation Checklist
              <span id="checkCount" style="font-size:13px;color:var(--ink-60);font-family:var(--sans);font-weight:600;">${checkedCount}/${totalChecks}</span>
            </h2>
            <div class="checklist-progress-bar">
              <i id="checkBar" style="width:${Math.round((checkedCount / totalChecks) * 100)}%;"></i>
            </div>
            <ul class="check-list" id="checkList">
              ${checklistHtml}
            </ul>
            <div class="checklist-complete-badge" id="completeBadge" ${checkedCount === totalChecks ? "" : 'style="display:none;"'}>
              ✓ All preparations complete! You are ready to present.
            </div>
          </article>
        </aside>
      </div>`;

    // Wire interactive checkboxes
    const checkItems = meetRoot.querySelectorAll(".check-item");
    const checkBar = document.getElementById("checkBar");
    const checkCount = document.getElementById("checkCount");
    const completeBadge = document.getElementById("completeBadge");

    checkItems.forEach(item => {
      const idx = item.dataset.idx;
      const checkbox = item.querySelector('input[type="checkbox"]');

      checkbox.addEventListener("change", () => {
        savedChecks[idx] = checkbox.checked;
        item.classList.toggle("completed", checkbox.checked);

        try {
          localStorage.setItem(storageKey, JSON.stringify(savedChecks));
        } catch (_) {}

        checkedCount = CHECKLIST_ITEMS.filter((_, i) => !!savedChecks[i]).length;
        if (checkCount) checkCount.textContent = `${checkedCount}/${totalChecks}`;
        if (checkBar) checkBar.style.width = `${Math.round((checkedCount / totalChecks) * 100)}%`;
        if (completeBadge) {
          completeBadge.style.display = (checkedCount === totalChecks) ? "block" : "none";
        }
      });
    });
  }

  async function loadData() {
    const ctx = VQContext.fromLocation() || VQContext.read() || {};

    const showEmpty = (msg) => {
      const researchUrl = typeof VQContext !== "undefined" ? VQContext.href("research.html") : "research.html";
      meetRoot.innerHTML = `<div class="empty-state">${esc(msg)} <a href="${researchUrl}">Start a new research</a>.</div>`;
    };

    if (!ctx.briefing_id && !ctx.research_id) {
      showEmpty("No active meeting research loaded.");
      return;
    }

    try {
      let briefingId = ctx.briefing_id;
      if (!briefingId && ctx.research_id) {
        const r = await VQApi.getResearch(ctx.research_id);
        briefingId = r.briefing_id;
        if (!briefingId && r.status === "completed") {
          const gen = await VQApi.generateBriefing(ctx.research_id, false);
          briefingId = gen.briefing_id;
        }
      }

      if (!briefingId) {
        showEmpty("Research briefing is still in progress. Please wait.");
        return;
      }

      let b = await VQApi.getBriefing(briefingId);
      if (b.status === "running" || b.status === "queued") {
        meetRoot.innerHTML = `<div class="empty-state">Briefing is generating. Please wait a moment…</div>`;
        for (let i = 0; i < 45; i++) {
          await sleep(1500);
          b = await VQApi.getBriefing(briefingId);
          if (b.status === "completed" || b.status === "failed") break;
        }
      }

      if (b.status !== "completed" || !b.briefing) {
        showEmpty((b.error && b.error.message) || "Could not load meeting preparation data.");
        return;
      }

      // Preserve context
      VQContext.write({
        research_id: b.research_id,
        briefing_id: b.briefing_id,
        entity_name: (b.briefing.entity && b.briefing.entity.name) || ctx.entity_name || ""
      });

      renderPreparation(b.briefing);

      // Wire navigation buttons
      if (backIntel) {
        backIntel.setAttribute("href", VQContext.href("intelligence.html"));
      }
      if (toStudio) {
        toStudio.setAttribute("href", VQContext.href("studio.html"));
      }
    } catch (err) {
      console.error("[VelQora Meeting Prep]", err);
      showEmpty(err.message || "Failed to load meeting preparation.");
    }
  }

  loadData();
})();
