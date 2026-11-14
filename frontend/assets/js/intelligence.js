/* VelQora Research Intelligence & Source Verification Controller */
(function(){
  const intelPanel = document.getElementById("panelIntel");
  const verifyPanel = document.getElementById("panelVerify");
  const tabIntel = document.getElementById("tabIntel");
  const tabVerify = document.getElementById("tabVerify");
  const intelTitle = document.getElementById("intelTitle");
  const intelLead = document.getElementById("intelLead");
  const toMeeting = document.getElementById("toMeeting");

  if (!intelPanel || !verifyPanel) return;

  function safeUrl(u) {
    return /^https?:\/\//i.test(String(u || "")) ? String(u) : "#";
  }

  function renderList(items, emptyText, isAnalysis = false) {
    if (!items || !items.length) {
      return `<p class="muted">${esc(emptyText || "Not available from retrieved sources.")}</p>`;
    }
    return `<ul>${items.map(i => {
      const text = typeof i === "string" ? i : (i.text || "");
      const date = (i.date) ? ` <span class="muted">(${esc(i.date)})</span>` : "";
      const isAi = isAnalysis || i.kind === "analysis" || i.verification_status === "analysis";
      const badge = isAi
        ? `<span class="kind-ai">AI analysis</span>`
        : (i.verification_status && i.verification_status !== "verified"
            ? `<span class="status-badge status-${esc(i.verification_status)}">${esc(i.verification_status)}</span>`
            : "");
      const sources = (i.source_ids && i.source_ids.length && !isAi)
        ? `<span class="src-tags">${i.source_ids.map(s => `<span class="src-tag">${esc(s)}</span>`).join("")}</span>`
        : "";
      return `<li>${esc(text)}${date}${sources}${badge}</li>`;
    }).join("")}</ul>`;
  }

  function renderIntel(b) {
    const people = (b.key_people || []).length
      ? `<div class="people-row">${b.key_people.map(p => {
          const initial = esc((p.name || "?").trim().charAt(0).toUpperCase());
          const name = esc(p.name);
          const role = esc(p.role || "Leadership");
          const srcs = (p.source_ids && p.source_ids.length)
            ? `<span class="src-tags">${p.source_ids.map(s => `<span class="src-tag">${esc(s)}</span>`).join("")}</span>`
            : "";
          return `<div class="person-card">
            <b>${initial}</b>
            <div>
              <div class="p-name">${name} ${srcs}</div>
              <div class="p-role">${role}</div>
            </div>
          </div>`;
        }).join("")}</div>`
      : `<p class="muted">No key people could be verified from retrieved sources.</p>`;

    // Relevant research findings combines verified developments and business insights
    const findings = [].concat(b.recent_developments || [], b.business_insights || []).filter(i => i.verification_status === "verified");

    // Industry Trends derives from industry tags and AI analysis
    const trends = (b.industry_information || []).filter(i => i.kind === "analysis");
    const tagsHtml = (b.industry_tags && b.industry_tags.length)
      ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;">${b.industry_tags.map(t => `<span class="kind-ai">${esc(t)}</span>`).join("")}</div>`
      : "";

    intelPanel.innerHTML = `
      <div class="intel-grid">
        <article class="intel-card wide">
          <h2>Company Overview</h2>
          <p style="font-size:15px;line-height:1.6;color:var(--navy);">${esc(b.overview || "No verified overview could be established from retrieved sources.")}</p>
        </article>

        <article class="intel-card">
          <h2>Company Background</h2>
          ${renderList(b.overview_items, "No additional background items were verified from retrieved sources.")}
        </article>

        <article class="intel-card">
          <h2>Key People and Leadership</h2>
          ${people}
        </article>

        <article class="intel-card">
          <h2>Recent Developments</h2>
          ${renderList(b.recent_developments, "No dated developments found in the 30-day research window.")}
        </article>

        <article class="intel-card">
          <h2>Important News</h2>
          ${renderList(b.important_news, "No dated news articles confirmed within the research window.")}
        </article>

        <article class="intel-card">
          <h2>Business Insights</h2>
          ${renderList(b.business_insights, "No business insights established from retrieved sources.")}
        </article>

        <article class="intel-card">
          <h2>Industry Information</h2>
          ${renderList((b.industry_information || []).filter(i => i.kind !== "analysis"), "No specific industry claims verified.")}
          ${tagsHtml}
        </article>

        <article class="intel-card">
          <h2>Industry Trends</h2>
          ${renderList(trends, "Trend commentary is labelled as AI analysis when available.", true)}
        </article>

        <article class="intel-card wide">
          <h2>Relevant Research Findings</h2>
          ${renderList(findings.slice(0, 8), "No additional verified research findings available.")}
        </article>
      </div>`;
  }

  function renderVerify(b) {
    const s = b.verification_summary || {};
    const total = s.total_claims || 0;
    const verified = s.verified_claims || 0;
    const unverified = s.unverified_claims || 0;
    const undated = s.undated_claims || 0;

    const undatedList = b.undated_information || [];
    const outdatedCount = undatedList.filter(i => i.verification_status === "outdated").length;
    const pct = total ? Math.round((verified / total) * 100) : 0;

    const sources = b.sources || [];

    // Map claim texts to cited source IDs
    const claims = [].concat(
      b.overview_items || [],
      b.recent_developments || [],
      b.important_news || [],
      b.business_insights || [],
      b.industry_information || []
    );
    const claimMap = {};
    claims.forEach(c => {
      (c.source_ids || []).forEach(sid => {
        if (!claimMap[sid]) claimMap[sid] = [];
        if (claimMap[sid].length < 3) claimMap[sid].push(c.text);
      });
    });

    verifyPanel.innerHTML = `
      <div class="v-stats">
        <div class="v-stat stat-total"><strong>${total}</strong><span>Total Claims</span></div>
        <div class="v-stat stat-verified"><strong>${verified}</strong><span>Verified</span></div>
        <div class="v-stat stat-unverified"><strong>${unverified}</strong><span>Unverified</span></div>
        <div class="v-stat stat-undated"><strong>${undated}</strong><span>Undated</span></div>
        <div class="v-stat stat-outdated"><strong>${outdatedCount}</strong><span>Outdated</span></div>
        <div class="v-stat stat-pct"><strong>${pct}%</strong><span>Verification</span></div>
      </div>

      <div class="vq-note" style="margin-bottom:18px;padding:12px 16px;border-radius:var(--r-sm);background:rgba(255,255,255,.7);border:1px solid var(--ink-12);">
        <strong>Grounding policy:</strong> Claims are marked <em>Verified</em> only when specific numbers, proper nouns, and key word stems match retrieved sources. AI-generated commentary is never counted as verified fact.
      </div>

      <article class="intel-card wide">
        <h2>Retrieved Sources &amp; Grounding Evidence (${sources.length})</h2>
        <div class="src-list">
          ${sources.length ? sources.map(src => {
            const st = src.verification_status || (src.supports_claims && src.supports_claims.length ? "verified" : "unverified");
            const associated = (src.supports_claims || []).concat(claimMap[src.source_id] || []);
            const uniqueAssoc = [...new Set(associated)].slice(0, 3);
            const statusClass = (st === "verified") ? "status-verified" : ((st === "unverified") ? "status-unverified" : "status-undated");

            return `<div class="src-row">
              <div class="src-header">
                <div>
                  <a href="${esc(safeUrl(src.url))}" target="_blank" rel="noopener noreferrer" class="src-link">
                    ${esc(src.title || src.url)} ↗
                  </a>
                  <div class="src-meta" style="margin-top:4px;">
                    <span><strong>Publisher:</strong> ${esc(src.publisher || "Web Source")}</span> · 
                    <span><strong>Date:</strong> ${esc(src.published_date || "Undated")}</span> · 
                    <span><strong>ID:</strong> ${esc(src.source_id || "")}</span>
                  </div>
                </div>
                <span class="status-badge ${statusClass}">${esc(st)}</span>
              </div>
              ${uniqueAssoc.length ? `
                <div class="src-claims">
                  <strong>Associated Claims:</strong> ${esc(uniqueAssoc.join(" — "))}
                </div>` : ""}
            </div>`;
          }).join("") : `<p class="muted">No sources were retrieved for this research.</p>`}
        </div>
      </article>

      ${undatedList.length ? `
        <article class="intel-card wide" style="margin-top:16px;">
          <h2>Undated or Outdated Information</h2>
          <p class="muted" style="margin-bottom:8px;font-size:13px;">Claims that are grounded in sources, but outside the 30-day window or lacking a reliable date:</p>
          ${renderList(undatedList, "")}
        </article>` : ""}

      ${(b.unverified_claims || []).length ? `
        <article class="intel-card wide" style="margin-top:16px;">
          <h2>Unverified Claims</h2>
          <p class="muted" style="margin-bottom:8px;font-size:13px;">Statements that could not be grounded in any retrieved source:</p>
          ${renderList(b.unverified_claims, "")}
        </article>` : ""}
    `;
  }

  function setupTabs() {
    function show(which) {
      const isIntel = which === "intel";
      intelPanel.hidden = !isIntel;
      verifyPanel.hidden = isIntel;
      tabIntel.setAttribute("aria-selected", isIntel ? "true" : "false");
      tabVerify.setAttribute("aria-selected", isIntel ? "false" : "true");
    }

    tabIntel.addEventListener("click", () => show("intel"));
    tabVerify.addEventListener("click", () => show("verify"));

    if (location.hash === "#verification") {
      show("verify");
    }
  }

  async function loadData() {
    const ctx = VQContext.fromLocation() || VQContext.read() || {};
    const showEmpty = (msg) => {
      intelPanel.innerHTML = `<div class="empty-state">${esc(msg)} <a href="research.html">Start a new research</a>.</div>`;
      verifyPanel.innerHTML = `<div class="empty-state">${esc(msg)} <a href="research.html">Start a new research</a>.</div>`;
    };

    if (!ctx.briefing_id && !ctx.research_id) {
      showEmpty("No active research loaded yet.");
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
        showEmpty("Research is still in progress. Please wait for completion.");
        return;
      }

      let b = await VQApi.getBriefing(briefingId);
      if (b.status === "running" || b.status === "queued") {
        intelPanel.innerHTML = `<div class="empty-state">Briefing is generating. Please wait a moment…</div>`;
        verifyPanel.innerHTML = `<div class="empty-state">Briefing is generating. Please wait a moment…</div>`;
        for (let i = 0; i < 45; i++) {
          await sleep(1500);
          b = await VQApi.getBriefing(briefingId);
          if (b.status === "completed") break;
        }
      }

      if (b.status !== "completed" || !b.briefing) {
        showEmpty((b.error && b.error.message) || "Could not retrieve completed briefing.");
        return;
      }

      // Preserve full context
      VQContext.write({
        research_id: b.research_id,
        briefing_id: b.briefing_id,
        entity_name: (b.briefing.entity && b.briefing.entity.name) || ctx.entity_name || ""
      });

      const entityName = b.briefing.entity && b.briefing.entity.name;
      if (entityName) {
        if (intelTitle) intelTitle.textContent = entityName + " — Intelligence";
        if (intelLead) intelLead.textContent = `Verified findings, leadership profiles, and source status for ${entityName}.`;
        document.title = `${entityName} — Intelligence · VelQora`;
      }

      renderIntel(b.briefing);
      renderVerify(b.briefing);

      if (toMeeting) {
        toMeeting.setAttribute("href", VQContext.href("meeting.html"));
      }
    } catch (err) {
      console.error("[VelQora Intelligence]", err);
      showEmpty(err.message || "Failed to load research intelligence.");
    }
  }

  setupTabs();
  loadData();
})();
