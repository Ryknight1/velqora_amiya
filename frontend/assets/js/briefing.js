/* ============================================================
   VelQora briefing rendering.
   1) Landing page: fills the three cards (intelligence / sources / preparation) with REAL backend data,
      keeping the original skeleton -> reveal animation.
   2) briefing.html: renders the full one-page briefing (all 10 sections).
   Every dynamic value goes through esc() — AI/web text is never injected as HTML.
   ============================================================ */
const icon=p=>`<span class="ico"><svg viewBox="0 0 24 24">${p}</svg></span>`;
const ul=(a,empty)=>`<ul>${(a&&a.length?a:[empty||"Not available from retrieved sources."]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
const words=t=>String(t).split(" ").filter(Boolean).map(w=>`<span class="wd${reduce?" on":""}">${esc(w)}</span>`).join(" ");
const shortDate=iso=>{if(!iso)return "";const d=new Date(iso+"T00:00:00");return isNaN(d)?"":d.toLocaleDateString(undefined,{day:"numeric",month:"short"});};
const displayUrl=u=>{try{const p=new URL(u);return (p.hostname.replace(/^www\./,"")+(p.pathname==="/"?"":p.pathname)).slice(0,60);}catch(_){return String(u).slice(0,60);}};

const VelQora={
  /* Placeholder content for the skeleton state (hidden behind the shimmer, never shown as data). */
  idleView(){
    return {
      intel:{entity:"—",tag:"Awaiting research",overview:"…",people:[{n:"—",r:""}],developments:["…"],insights:["…"],industry:["…"]},
      sources:{items:[0,1,2].map(()=>({n:"…",u:"…",href:"#",t:"…",i:"·",ok:true})),verifiedCount:0,total:0,pct:0,chipOk:true,chipText:"Verified"},
      prep:{talking:["…"],questions:["…"],risks:["…"],href:null,chip:"Ready"}
    };
  },

  /* Map the API briefing -> what the three cards display. */
  toView(b){
    const sum=b.verification_summary||{verified_claims:0,total_claims:0};
    const days=b.research_period?Math.round((new Date(b.research_period.end_date)-new Date(b.research_period.start_date))/864e5):30;
    const dated=a=>a.map(i=>i.date?`${i.text} (${shortDate(i.date)})`:i.text);
    const rank=s=>({verified:0,undated:1,unverified:2}[s.verification_status]??3);
    const top=[...(b.sources||[])].sort((x,y)=>rank(x)-rank(y)).slice(0,3);
    const ai=b.ai&&b.ai.analysis_available;
    const noAi="Not generated — AI analysis unavailable";
    return {
      intel:{
        entity:b.entity.name, tag:"Live research",
        overview:b.overview||"No verified overview could be established from the retrieved sources.",
        people:(b.key_people||[]).map(p=>({n:p.name,r:p.role||""})),
        developments:dated(b.recent_developments||[]),
        devEmpty:`No verified developments in the last ${days} days.`,
        insights:(b.business_insights||[]).map(i=>i.text),
        industry:b.industry_tags||[],
        industryText:(b.industry_information||[]).map(i=>i.text)
      },
      sources:{
        items:top.map(s=>({n:s.title,u:displayUrl(s.url),href:s.url,t:s.age_label||"undated",i:Array.from(s.publisher||"?")[0].toUpperCase(),ok:s.verification_status==="verified"})),
        verifiedCount:sum.verified_claims,total:sum.total_claims,
        pct:sum.total_claims?Math.round(sum.verified_claims/sum.total_claims*100):0,
        chipOk:sum.verified_claims>0,chipText:sum.verified_claims>0?"Verified":"Unverified"
      },
      prep:{
        talking:(b.meeting_talking_points||[]).slice(0,3).map(i=>i.text),
        questions:(b.suggested_questions||[]).slice(0,3).map(i=>i.text),
        risks:(b.potential_risks||[]).slice(0,3).map(i=>i.text),
        empty:ai?"None identified from the sources.":noAi,
        href:"briefing.html?id="+encodeURIComponent(b.briefing_id),chip:"Ready"
      }
    };
  },

  render(d,pending=false){
    const P=pending?" pending":"";
    const i=d.intel;
    const people=i.people.length
      ? `<div class="people">${i.people.map(p=>`<div class="person"><b>${esc(Array.from(p.n)[0]||"?")}</b>${esc(p.n)}<small>${esc(p.r)}</small></div>`).join("")}</div>`
      : `<p>None verified from the retrieved sources.</p>`;
    const industry=i.industry.length
      ? `<div class="tags">${i.industry.map(t=>`<span>${esc(t)}</span>`).join("")}</div>`
      : (i.industryText&&i.industryText.length?ul(i.industryText.slice(0,2)):`<p>No verified industry information.</p>`);
    $("#intel").innerHTML=`
      <div class="ch"><div class="ct">${icon('<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>')}Research Intelligence</div><span class="chip">${esc(i.tag)}</span></div>
      <div class="sec${P}"><h4>Company Overview · ${esc(i.entity)}</h4><p>${words(i.overview)}</p></div>
      <div class="sec${P}"><h4>Key People</h4>${people}</div>
      <div class="sec${P}"><h4>Recent Developments</h4>${ul(i.developments,i.devEmpty)}</div>
      <div class="sec${P}"><h4>Business Insights</h4>${ul(i.insights,"No verified insights available.")}</div>
      <div class="sec${P}"><h4>Industry Information</h4>${industry}</div>`;

    const s=d.sources;
    const rows=s.items.length?s.items.map(x=>`<div class="src${P}${x.ok?"":" unv"}"><span class="fav">${esc(x.i)}</span><div class="m"><b>${esc(x.n)}</b><a href="${esc(safeHref(x.href))}" target="_blank" rel="noopener noreferrer">${esc(x.u)}</a></div><time>${esc(x.t)}</time><span class="tick"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span></div>`).join("")
      :`<div class="src unv"><div class="m"><b>No relevant sources found</b></div></div>`;
    $("#sources").innerHTML=`
      <div class="ch"><div class="ct">${icon('<path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6l8-3zM8.5 12l2.5 2.5L16 9.5"/>')}Source Verification</div><span class="chip${s.chipOk?" ok":""}">${esc(s.chipText)}</span></div>
      ${rows}
      <div class="verify${P}" style="--pct:${Number(s.pct)||0}%"><span><b id="vcount">${pending?0:s.verifiedCount}</b> of ${Number(s.total)||0} claims verified</span><div class="bar"><i></i></div></div>`;

    const m=d.prep, e=m.empty;
    const chip=m.href?`<a class="chip" href="${esc(m.href)}" target="_blank" rel="noopener" title="Open the full one-page briefing">${esc(m.chip)}</a>`:`<span class="chip">${esc(m.chip)}</span>`;
    $("#prep").innerHTML=`
      <div class="ch"><div class="ct">${icon('<path d="M4 5h16v11H9l-5 4z"/>')}Meeting Preparation</div>${chip}</div>
      <div class="pgroup${P}"><h4>Talking Points</h4>${ul(m.talking,e)}</div>
      <div class="pgroup${P}"><h4>Suggested Questions</h4>${ul(m.questions,e)}</div>
      <div class="pgroup${P}"><h4>Potential Discussion Risks</h4>${ul(m.risks,e)}</div>`;
  },

  /* Original reveal choreography — now driven by data that has really arrived. */
  _id:0,
  async reveal(d){
    const id=++this._id, alive=()=>id===this._id;
    if(reduce){ this.render(d,false); return; }
    this.render(d,true);
    const show=async(el,gap=0)=>{ if(!el) return; el.classList.remove("pending"); if(gap) await sleep(gap); };
    const intel=$$("#intel .sec"), srcs=$$("#sources .src"), groups=$$("#prep .pgroup");

    await show(intel[0]);
    for(const w of $$("#intel .wd")){ w.classList.add("on"); await sleep(28); if(!alive())return; }
    await sleep(150);
    await show(intel[1],450); if(!alive())return;
    await show(intel[2],450); if(!alive())return;
    for(const s of srcs){ await show(s,380); if(!alive())return; }
    await show(intel[3],250); await show(intel[4],200);
    const v=$(".verify"); if(v) v.classList.remove("pending");
    countTo($("#vcount"),d.sources.verifiedCount,1100);
    await sleep(700); if(!alive())return;
    for(const g of groups){ await show(g,450); if(!alive())return; }
  },

  renderIdle(){ this._id++; this.render(this.idleView(),true); }   /* skeleton is always the shimmer state */
};

function countTo(el,n,ms){
  if(!el) return;
  const t0=performance.now();
  const f=t=>{const k=Math.min((t-t0)/ms,1);el.textContent=Math.round(n*(1-Math.pow(1-k,3)));if(k<1)requestAnimationFrame(f)};
  requestAnimationFrame(f);
}

/* ============================================================
   Full briefing page (briefing.html)
   ============================================================ */
const BriefPage={
  refs(ids){
    return ids&&ids.length?`<span class="refs">${ids.map(s=>`<a href="#src-${esc(s)}">[${esc(s)}]</a>`).join(" ")}</span>`:"";
  },
  li(i,{ai=false}={}){
    const when=i.date?`<span class="muted"> · ${esc(shortDate(i.date))}</span>`:"";
    return `<li><span>${esc(i.text)}${when}${ai?'<span class="tag-ai">AI analysis</span>':""}${this.refs(i.source_ids)}</span></li>`;
  },
  list(items,opts){
    return items&&items.length?`<ul>${items.map(i=>this.li(i,opts)).join("")}</ul>`:`<p class="muted">Not available from the retrieved sources.</p>`;
  },
  sec(n,title,body,chip=""){
    return `<section class="bsec"><h2>${typeof n==="number"?n+". ":""}${esc(title)} ${chip}</h2>${body}</section>`;
  },
  render(b){
    const sum=b.verification_summary, pct=sum.total_claims?Math.round(sum.verified_claims/sum.total_claims*100):0;
    const ok='<span class="chip ok">Verified</span>', ai='<span class="chip">AI analysis</span>';
    const meta=[
      b.entity.type!=="unknown"?b.entity.type:null,
      `Research period ${b.research_period.start_date} → ${b.research_period.end_date}`,
      b.meeting.purpose?`Purpose: ${b.meeting.purpose}`:null,
      b.meeting.time?`Meeting: ${b.meeting.time}`:null,
      `Generated ${new Date(b.generated_at).toLocaleString()}`,
      b.ai.analysis_available&&b.ai.model?`Model: ${b.ai.model}`:null
    ].filter(Boolean).map(x=>`<span>${esc(x)}</span>`).join("");
    const people=b.key_people.length?`<ul>${b.key_people.map(p=>`<li><span><b>${esc(p.name)}</b>${p.role?` — ${esc(p.role)}`:""}${this.refs(p.source_ids)}</span></li>`).join("")}</ul>`:`<p class="muted">No key people could be verified from the retrieved sources.</p>`;
    const insights=(b.business_insights.length||b.industry_information.length||b.industry_tags.length)
      ?`${b.industry_tags.length?`<p>${b.industry_tags.map(t=>`<span class="tag-ai" style="margin:0 6px 6px 0;display:inline-block">${esc(t)}</span>`).join("")}</p>`:""}${this.list([...b.business_insights,...b.industry_information])}`
      :`<p class="muted">Not available from the retrieved sources.</p>`;
    const aiOff=!b.ai.analysis_available?`<p class="muted">AI analysis was unavailable for this briefing.</p>`:null;
    const sources=b.sources.length?b.sources.map(s=>`<div class="bsrc" id="src-${esc(s.source_id)}"><b>${esc(s.source_id)}</b><div><a href="${esc(safeHref(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a><small>${esc(s.publisher)} · ${s.published_date?esc(s.published_date):"undated"} · ${esc(s.source_type.replace("_"," "))} · ${esc(s.verification_status)}${s.supports_claims.length?` · supports ${esc(s.supports_claims.join(", "))}`:""}</small></div></div>`).join(""):`<p class="muted">No sources were retrieved.</p>`;
    const extra=[];
    if(b.undated_information.length) extra.push(this.sec("•","Not confirmed as recent",`<p class="muted">Grounded in a source, but the source is undated or older than the research period, so it is not listed as a recent development.</p>${this.list(b.undated_information)}`));
    if(b.unverified_claims.length) extra.push(this.sec("•","Unverified claims (excluded)",`<p class="muted">The AI drafted these but they could not be matched to retrieved sources. They are not part of the verified briefing.</p><ul>${b.unverified_claims.map(i=>`<li><span>${esc(i.text)}<span class="muted"> — ${esc(i.note||"")}</span></span></li>`).join("")}</ul>`));
    if(b.warnings.length) extra.push(`<section class="bsec"><h2>Notes</h2><ul>${b.warnings.map(w=>`<li><span>${esc(w)}</span></li>`).join("")}</ul></section>`);

    $("#briefRoot").innerHTML=`
      <div class="brief-head"><div class="eyebrow"><span class="dot"></span>Pre-meeting briefing</div><h1>${esc(b.entity.name)}</h1><div class="brief-meta">${meta}</div></div>
      <div class="brief-bar"><span><b>${sum.verified_claims}</b> of ${sum.total_claims} claims verified${sum.undated_claims?` · ${sum.undated_claims} undated`:""}${sum.unverified_claims?` · ${sum.unverified_claims} unverified`:""}</span><div class="bar"><i style="width:${pct}%"></i></div></div>
      <p class="vq-note">“Verified” means the claim’s wording and figures were found in a retrieved source. It does not guarantee the source itself is correct — check key facts before relying on them.</p>
      ${this.sec(1,"Company / Person Overview",b.overview_items.length?this.list(b.overview_items):`<p class="muted">No verified overview could be established.</p>`,ok)}
      ${this.sec(2,"Key People and Leadership",people,ok)}
      ${this.sec(3,`Recent Developments (${b.research_period.start_date} → ${b.research_period.end_date})`,this.list(b.recent_developments),ok)}
      ${this.sec(4,"Important News and Announcements",this.list(b.important_news),ok)}
      ${this.sec(5,"Business and Industry Insights",insights,ok)}
      ${this.sec(6,"Meeting Talking Points",aiOff||this.list(b.meeting_talking_points,{ai:true}),ai)}
      ${this.sec(7,"Suggested Questions",aiOff||this.list(b.suggested_questions,{ai:true}),ai)}
      ${this.sec(8,"Potential Discussion Risks",aiOff||(this.list(b.potential_risks,{ai:true})+(b.opportunities.length?`<h2 style="margin-top:12px;font-size:16px">Potential opportunities</h2>${this.list(b.opportunities,{ai:true})}`:"")),ai)}
      ${this.sec(9,"Verified Sources and References",sources)}
      ${this.sec(10,"Open Questions",this.list(b.open_questions))}
      ${extra.join("")}
      <div class="brief-actions"><button class="btn btn-coral" id="printBtn">Print / Save as PDF</button><a class="btn btn-ghost" href="index.html">← Back to VelQora</a></div>`;
    const pb=$("#printBtn"); if(pb) pb.addEventListener("click",()=>window.print());
    document.title=`${b.entity.name} — VelQora briefing`;
  },
  async init(){
    const root=$("#briefRoot"); if(!root) return;
    const id=new URLSearchParams(location.search).get("id")||"";
    const say=(t,err)=>{root.innerHTML=`<div class="brief-head"><h1>${err?"Briefing unavailable":"Loading briefing…"}</h1><p class="vq-note" style="margin-top:10px">${esc(t)}</p><div class="brief-actions"><a class="btn btn-ghost" href="index.html">← Back to VelQora</a></div></div>`;};
    if(!/^[a-f0-9]{32}$/.test(id)) return say("This link is missing a valid briefing id.",true);
    say("Fetching your briefing…");
    try{
      for(let i=0;i<90;i++){
        const r=await VQApi.getBriefing(id);
        if(r.status==="completed"&&r.briefing) return this.render(r.briefing);
        if(r.status==="failed") return say((r.error&&r.error.message)||"The briefing could not be generated.",true);
        say(r.message||"Preparing your brief…");
        await sleep(1500);
      }
      say("This is taking longer than expected. Reload to check again.",true);
    }catch(e){ say(e.message||"Could not load the briefing.",true); }
  }
};
BriefPage.init();
