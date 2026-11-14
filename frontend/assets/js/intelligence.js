(function(){
  const intel=$("#panelIntel"), verify=$("#panelVerify");
  if(!intel||!verify) return;
  const list=(items,empty)=>{
    if(!items||!items.length) return `<p class="muted">${esc(empty)}</p>`;
    return `<ul>${items.map(i=>{
      const t=typeof i==="string"?i:(i.text||"");
      const ai=i.kind==="analysis"?`<span class="kind-ai">AI analysis</span>`:"";
      const date=i.date?` <span class="muted">(${esc(i.date)})</span>`:"";
      const st=i.verification_status&&i.kind!=="analysis"?`<span class="status-${esc(i.verification_status)}"> ${esc(i.verification_status)}</span>`:"";
      return `<li>${esc(t)}${date}${st}${ai}</li>`;
    }).join("")}</ul>`;
  };
  function renderIntel(b){
    const people=(b.key_people||[]).length
      ? `<div class="people-row">${b.key_people.map(p=>`<div class="person-card"><b>${esc((p.name||"?").charAt(0))}</b><div><strong>${esc(p.name)}</strong><div class="muted">${esc(p.role||"")}</div></div></div>`).join("")}</div>`
      : `<p class="muted">No key people could be verified from retrieved sources.</p>`;
    intel.innerHTML=`<div class="intel-grid">
      <article class="intel-card wide"><h2>Company Overview</h2><p>${esc(b.overview||"No verified overview could be established from the retrieved sources.")}</p></article>
      <article class="intel-card"><h2>Company Background</h2>${list(b.overview_items,"No additional background items were verified.")}</article>
      <article class="intel-card"><h2>Key People and Leadership</h2>${people}</article>
      <article class="intel-card"><h2>Recent Developments</h2>${list(b.recent_developments,"No dated developments in the research window.")}</article>
      <article class="intel-card"><h2>Important News</h2>${list(b.important_news,"No important news items were verified.")}</article>
      <article class="intel-card"><h2>Business Insights</h2>${list(b.business_insights,"No verified business insights.")}</article>
      <article class="intel-card"><h2>Industry Information</h2>${list(b.industry_information,"No verified industry information.")}${b.industry_tags&&b.industry_tags.length?`<p>${b.industry_tags.map(t=>`<span class="kind-ai">${esc(t)}</span>`).join(" ")}</p>`:""}</article>
      <article class="intel-card"><h2>Industry Trends</h2>${list((b.industry_information||[]).filter(i=>i.kind==="analysis"),"Trend commentary is labelled as AI analysis when available.")}</article>
      <article class="intel-card wide"><h2>Relevant Research Findings</h2>${list([].concat(b.recent_developments||[],b.business_insights||[]).slice(0,8),"No additional findings.")}</article>
    </div>`;
  }
  function renderVerify(b){
    const s=b.verification_summary||{};
    const total=s.total_claims||0, pct=total?Math.round((s.verified_claims||0)/total*100):0;
    const claims=[].concat(b.overview_items||[],b.recent_developments||[],b.important_news||[],b.business_insights||[],b.industry_information||[]);
    const undated=b.undated_information||[];
    const sources=b.sources||[];
    const claimMap={};
    claims.forEach(c=>{(c.source_ids||[]).forEach(id=>{ (claimMap[id]=claimMap[id]||[]).push(c.text); });});
    verify.innerHTML=`
      <div class="v-stats">
        <div class="v-stat"><strong>${total}</strong><span>Total claims</span></div>
        <div class="v-stat"><strong class="status-verified">${s.verified_claims||0}</strong><span>Verified</span></div>
        <div class="v-stat"><strong class="status-unverified">${s.unverified_claims||0}</strong><span>Unverified</span></div>
        <div class="v-stat"><strong class="status-undated">${s.undated_claims||0}</strong><span>Undated</span></div>
        <div class="v-stat"><strong>${pct}%</strong><span>Verification</span></div>
      </div>
      <p class="vq-note">Verified means the claim wording was found in a retrieved source. It is not a guarantee that the source is correct. AI analysis is never counted as a verified fact.</p>
      <article class="intel-card wide"><h2>Sources</h2>
        ${sources.length?sources.map(src=>{
          const st=src.verification_status||"unverified";
          const associated=(src.supports_claims||[]).concat(claimMap[src.source_id]||[]).slice(0,4);
          return `<div class="src-row"><div>
            <a href="${esc(safeHref(src.url))}" target="_blank" rel="noopener noreferrer">${esc(src.title||src.url)}</a>
            <small>${esc(src.publisher||"Unknown publisher")} · ${esc(src.published_date||"undated")} · ${esc(src.source_id||"")}</small>
            ${associated.length?`<small>Claims: ${esc(associated.join(" · "))}</small>`:""}
          </div><span class="status-${esc(st)}">${esc(st)}</span></div>`;
        }).join(""):`<p class="muted">No sources were retrieved.</p>`}
      </article>
      ${undated.length?`<article class="intel-card wide"><h2>Undated or outdated information</h2>${list(undated,"")}</article>`:""}
      ${(b.unverified_claims||[]).length?`<article class="intel-card wide"><h2>Unverified claims</h2>${list(b.unverified_claims,"")}</article>`:""}
    `;
  }
  function tabs(){
    const ti=$("#tabIntel"), tv=$("#tabVerify");
    const show=(which)=>{
      const intelOn=which==="intel";
      intel.hidden=!intelOn; verify.hidden=intelOn;
      ti.setAttribute("aria-selected",intelOn?"true":"false");
      tv.setAttribute("aria-selected",intelOn?"false":"true");
    };
    ti.addEventListener("click",()=>show("intel"));
    tv.addEventListener("click",()=>show("verify"));
    if(location.hash==="#verification") show("verify");
  }
  async function load(){
    const ctx=VQContext.fromLocation()||{};
    const empty=(t)=>intel.innerHTML=`<div class="empty-state">${esc(t)} <a href="research.html">Start research</a>.</div>`;
    if(!ctx.briefing_id && !ctx.research_id) return empty("No research context yet.");
    try{
      let briefingId=ctx.briefing_id;
      if(!briefingId && ctx.research_id){
        const r=await VQApi.getResearch(ctx.research_id);
        briefingId=r.briefing_id;
        if(!briefingId && r.status==="completed"){
          const g=await VQApi.generateBriefing(ctx.research_id,false);
          briefingId=g.briefing_id;
        }
      }
      if(!briefingId) return empty("Research is not ready for intelligence yet.");
      const b=await VQApi.getBriefing(briefingId);
      if(b.status!=="completed"||!b.briefing) return empty(b.message||"Briefing is still preparing.");
      VQContext.write({research_id:b.research_id, briefing_id:b.briefing_id});
      const name=b.briefing.entity&&b.briefing.entity.name;
      if(name){ $("#intelTitle").textContent=name; document.title=name+" — Intelligence · VelQora"; }
      renderIntel(b.briefing); renderVerify(b.briefing);
    }catch(e){ empty(e.message||"Could not load intelligence."); }
  }
  tabs(); load();
  const to=$("#toMeeting"); if(to) to.setAttribute("href",VQContext.href("meeting.html"));
})();
