(function(){
  const root=$("#meetRoot"); if(!root) return;
  const CHECKS=[
    "Review company overview and recent developments",
    "Read verified sources for the claims you will cite",
    "Prepare answers around risks and open questions",
    "Choose 3 talking points to lead with",
    "Draft the opening 60 seconds of the conversation",
    "Export or rehearse the meeting presentation"
  ];
  const list=(items,ai=false,empty="Not available from the retrieved sources.")=>{
    if(!items||!items.length) return `<p class="muted">${esc(empty)}</p>`;
    return `<ul>${items.map(i=>`<li>${esc(i.text||i)}${ai?'<span class="kind-ai">AI analysis</span>':""}</li>`).join("")}</ul>`;
  };
  function strategy(b){
    const name=(b.entity&&b.entity.name)||"this meeting";
    const purpose=(b.meeting&&b.meeting.purpose)||"the discussion";
    const talk=(b.meeting_talking_points||[]).slice(0,2).map(i=>i.text).filter(Boolean);
    const risk=(b.potential_risks||[])[0];
    const parts=[`Walk in ready to discuss ${name} in the context of ${purpose}.`];
    if(talk.length) parts.push("Lead with: "+talk.join("; "));
    if(risk) parts.push("Watch for: "+risk.text);
    if(!b.ai||!b.ai.analysis_available) parts.push("AI analysis was limited for this briefing — stay with verified facts.");
    return parts.join(" ");
  }
  function render(b){
    const key=`vq_check_${b.briefing_id||"anon"}`;
    let saved={}; try{saved=JSON.parse(localStorage.getItem(key)||"{}");}catch(_){}
    const checks=CHECKS.map((t,i)=>`<li><input type="checkbox" id="ck${i}" ${saved[i]?"checked":""}><label for="ck${i}">${esc(t)}</label></li>`).join("");
    root.innerHTML=`<div class="meet-grid"><div>
      <article class="meet-card"><h2>Meeting Overview</h2>
        <p><strong>${esc((b.entity&&b.entity.name)||"Unknown")}</strong></p>
        <p class="muted">${esc((b.meeting&&b.meeting.time)||"Time not set")} · ${esc((b.meeting&&b.meeting.purpose)||"Purpose not set")}</p>
        <p>${esc(b.overview||"No verified overview.")}</p>
      </article>
      <article class="meet-card"><h2>Meeting Talking Points</h2>${list(b.meeting_talking_points,true)}</article>
      <article class="meet-card"><h2>Suggested Questions</h2>${list(b.suggested_questions,true)}</article>
      <article class="meet-card"><h2>Potential Risks</h2>${list(b.potential_risks,true)}</article>
      <article class="meet-card"><h2>Opportunities</h2>${list(b.opportunities,true)}</article>
      <article class="meet-card"><h2>Meeting Strategy</h2><p>${esc(strategy(b))}</p></article>
    </div>
    <aside>
      <article class="meet-card"><h2>Preparation Checklist</h2>
        <ul class="check-list">${checks}</ul>
      </article>
    </aside></div>`;
    root.querySelectorAll(".check-list input").forEach((el,i)=>{
      el.addEventListener("change",()=>{
        saved[i]=el.checked; try{localStorage.setItem(key,JSON.stringify(saved));}catch(_){}
      });
    });
  }
  async function load(){
    const ctx=VQContext.fromLocation()||{};
    const empty=t=>root.innerHTML=`<div class="empty-state">${esc(t)} <a href="research.html">Start research</a>.</div>`;
    if(!ctx.briefing_id && !ctx.research_id) return empty("No research context yet.");
    try{
      let id=ctx.briefing_id;
      if(!id){
        const r=await VQApi.getResearch(ctx.research_id);
        id=r.briefing_id;
      }
      if(!id) return empty("Complete research before meeting prep.");
      const b=await VQApi.getBriefing(id);
      if(b.status!=="completed"||!b.briefing) return empty(b.message||"Briefing not ready.");
      VQContext.write({research_id:b.research_id, briefing_id:b.briefing_id});
      render(b.briefing);
    }catch(e){ empty(e.message||"Could not load meeting prep."); }
  }
  load();
  const back=$("#backIntel"), studio=$("#toStudio");
  if(back) back.setAttribute("href",VQContext.href("intelligence.html"));
  if(studio) studio.setAttribute("href",VQContext.href("studio.html"));
})();
