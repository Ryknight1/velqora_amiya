/* VelQora Research Workspace:
   - Input validation
   - Real backend submission (POST /api/research)
   - Real status polling (GET /api/research/{id} and GET /api/briefing/{id})
   - Real backend progress stages (never fabricated)
   - Session persistence and resume across page refresh
   - Seamless navigation to intelligence.html
*/
(function(){
  const form = document.getElementById("researchForm");
  const goBtn = document.getElementById("goBtn");
  if (!form || !goBtn) return;

  const rName = document.getElementById("rName");
  const rUrl = document.getElementById("rUrl");
  const rTime = document.getElementById("rTime");
  const rType = document.getElementById("rType");
  const rPurpose = document.getElementById("rPurpose");

  const statusWrap = document.getElementById("statusWrap");
  const stageMsg = document.getElementById("stageMsg");
  const stagePct = document.getElementById("stagePct");
  const progBar = document.getElementById("progBar");
  const stageList = document.getElementById("stageList");
  const vqMsg = document.getElementById("vqMsg");
  const nextIntel = document.getElementById("nextIntel");
  const activeBanner = document.getElementById("activeBanner");
  const activeEntityName = document.getElementById("activeEntityName");
  const activeIntelLink = document.getElementById("activeIntelLink");

  const STAGES = [
    "validating",
    "searching",
    "processing",
    "date_validation",
    "analyzing",
    "verifying",
    "preparing",
    "completed"
  ];

  const MAX_POLL_MS = 8 * 60 * 1000;
  let running = false;

  function showMsg(text, kind = "error") {
    if (!vqMsg) return;
    if (!text) {
      vqMsg.hidden = true;
      vqMsg.textContent = "";
      return;
    }
    vqMsg.textContent = text;
    vqMsg.className = "vq-msg" + (kind === "info" ? " info" : "");
    vqMsg.hidden = false;
  }

  function setBusy(isBusy, buttonText) {
    running = isBusy;
    goBtn.disabled = isBusy;
    goBtn.classList.toggle("busy", isBusy);
    const inputs = form.querySelectorAll("input, select, textarea");
    inputs.forEach(el => el.disabled = isBusy);
    if (buttonText) {
      goBtn.innerHTML = buttonText;
    } else {
      goBtn.innerHTML = isBusy ? 'Researching… <span class="arr">⏳</span>' : 'Start Research <span class="arr">→</span>';
    }
  }

  function updateProgress(progress, message, stage) {
    if (statusWrap) statusWrap.hidden = false;
    const pct = Math.max(0, Math.min(100, Number(progress) || 0));
    if (progBar) progBar.style.width = pct + "%";
    if (stagePct) stagePct.textContent = pct + "%";
    if (stageMsg && message) stageMsg.textContent = message;

    if (stageList && stage) {
      stageList.replaceChildren();
      const currentIdx = STAGES.indexOf(stage);
      STAGES.forEach((s, idx) => {
        const pill = document.createElement("span");
        let cls = "stage-pill";
        const isDone = (currentIdx !== -1 && idx < currentIdx) || stage === "completed";
        if (s === stage && stage !== "completed") {
          cls += " on";
        } else if (isDone) {
          cls += " done";
        }
        pill.className = cls;
        pill.textContent = (isDone ? "✓ " : "") + s.replace(/_/g, " ");
        stageList.appendChild(pill);
      });
    }
  }

  async function pollJob(fetcher, onTick) {
    const start = Date.now();
    let consecutiveFails = 0;
    while (true) {
      if (Date.now() - start > MAX_POLL_MS) {
        throw new VQApi.ApiError(0, "timeout", "The research request timed out. Please check your network connection or try again.");
      }
      await sleep(Date.now() - start > 30000 ? 2000 : 1200);
      try {
        const res = await fetcher();
        consecutiveFails = 0;
        if (onTick) onTick(res);
        if (res.status === "completed" || res.status === "failed") {
          return res;
        }
      } catch (err) {
        if ([401, 404, 422].includes(err.status) || ++consecutiveFails >= 5) {
          throw err;
        }
      }
    }
  }

  function validateInput() {
    const name = rName.value.trim();
    if (!name || name.length < 2) {
      showMsg("Enter a company or executive name to begin research.");
      rName.focus();
      return null;
    }
    const url = rUrl.value.trim();
    if (url) {
      if (/^(javascript|data|file|ftp):/i.test(url)) {
        showMsg("Please enter a valid web URL starting with http:// or https://");
        rUrl.focus();
        return null;
      }
    }
    return {
      name,
      url: url || null,
      meeting_time: rTime.value.trim() || null,
      purpose: rPurpose.value.trim() || null,
      entity_type: rType.value || "auto",
      auto_brief: true
    };
  }

  async function followThroughBriefing(researchJob, entityName) {
    let briefingId = researchJob.briefing_id;
    if (!briefingId) {
      updateProgress(80, "Synthesizing executive briefing…", "analyzing");
      const gen = await VQApi.generateBriefing(researchJob.research_id, false);
      briefingId = gen.briefing_id;
    }

    let b = await VQApi.getBriefing(briefingId);
    if (b.status !== "completed") {
      b = await pollJob(() => VQApi.getBriefing(briefingId), tick => {
        updateProgress(tick.progress || 85, tick.message || "Generating briefing…", tick.stage || "preparing");
      });
    }

    if (b.status === "failed") {
      const err = b.error || {};
      throw new VQApi.ApiError(0, err.code || "briefing_failed", err.message || "Briefing could not be generated.");
    }

    updateProgress(100, "Briefing ready ✓", "completed");
    VQContext.write({
      research_id: researchJob.research_id,
      briefing_id: b.briefing_id,
      entity_name: (b.briefing && b.briefing.entity && b.briefing.entity.name) || entityName
    });

    await sleep(600);
    location.href = VQContext.href("intelligence.html");
  }

  async function startResearch(e) {
    if (e) e.preventDefault();
    if (running) return;
    showMsg("");

    const payload = validateInput();
    if (!payload) return;

    setBusy(true, 'Starting research… <span class="arr">⏳</span>');
    updateProgress(4, "Validating request…", "validating");

    try {
      const job = await VQApi.startResearch(payload);
      VQContext.write({
        research_id: job.research_id,
        briefing_id: job.briefing_id || null,
        entity_name: payload.name
      });

      // Update URL without page reload so refresh preserves the job
      try {
        const newUrl = new URL(location.href);
        newUrl.searchParams.set("research_id", job.research_id);
        history.replaceState(null, "", newUrl.toString());
      } catch (_) {}

      updateProgress(job.progress || 8, job.message || "Searching the web…", job.stage || "searching");

      const done = await pollJob(() => VQApi.getResearch(job.research_id), tick => {
        updateProgress(tick.progress, tick.message, tick.stage);
        if (tick.briefing_id) {
          VQContext.write({ research_id: tick.research_id, briefing_id: tick.briefing_id });
        }
      });

      if (done.status === "failed") {
        const err = done.error || {};
        throw new VQApi.ApiError(0, err.code || "failed", err.message || "Research failed. Please try again.");
      }

      await followThroughBriefing(done, payload.name);

    } catch (err) {
      console.error("[VelQora Research]", err);
      let errorText = err.message || "Research could not be completed. Please try again.";
      if (err.code === "tavily_not_configured") {
        errorText = "Search provider is not configured. Add TAVILY_API_KEY to the server configuration.";
      } else if (err.code === "bifrost_not_configured") {
        errorText = "AI analysis service is not configured. Set BIFROST_BASE_URL and BIFROST_MODEL in the server environment.";
      } else if (err.code === "network") {
        errorText = "Unable to connect to the VelQora API. Please verify your connection or ensure the server is running.";
      }
      showMsg(errorText, "error");
      setBusy(false, 'Retry Research <span class="arr">→</span>');
    }
  }

  form.addEventListener("submit", startResearch);

  // Resume workflow on page load or refresh
  async function checkExistingContext() {
    const ctx = VQContext.fromLocation() || VQContext.read();
    if (!ctx || !ctx.research_id) return;

    if (nextIntel) {
      nextIntel.setAttribute("href", VQContext.href("intelligence.html"));
    }

    try {
      const r = await VQApi.getResearch(ctx.research_id);
      const entityName = (r.entity && r.entity.name) || ctx.entity_name || "";

      if (r.status === "queued" || r.status === "running") {
        // Automatically resume in-progress job
        if (rName && entityName) rName.value = entityName;
        setBusy(true, 'Resuming research… <span class="arr">⏳</span>');
        updateProgress(r.progress || 10, r.message || "Researching…", r.stage || "searching");

        const done = await pollJob(() => VQApi.getResearch(ctx.research_id), tick => {
          updateProgress(tick.progress, tick.message, tick.stage);
        });

        if (done.status === "completed") {
          await followThroughBriefing(done, entityName);
        } else {
          showMsg((done.error && done.error.message) || "Research failed.", "error");
          setBusy(false);
        }
      } else if (r.status === "completed") {
        // Show banner informing user of ready research
        if (activeBanner && entityName) {
          activeBanner.hidden = false;
          if (activeEntityName) activeEntityName.textContent = entityName;
          if (activeIntelLink) activeIntelLink.setAttribute("href", VQContext.href("intelligence.html"));
        }
      }
    } catch (_) {
      // If research id no longer valid, gracefully ignore
    }
  }

  checkExistingContext();

  // Health check warning if backend down
  VQApi.health().catch(e => {
    if (e.code === "network") {
      showMsg("Unable to connect to the VelQora API server. Please check your connection and refresh.", "error");
    }
  });
})();
