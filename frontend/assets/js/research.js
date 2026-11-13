/* ============================================================
   VelQora research flow (landing-page input card).
   Real inputs -> POST /api/research -> poll real progress -> render the real briefing.
   No simulated research: the status text and progress bar mirror what the server reports.
   ============================================================ */
(function(){
  const goBtn=$("#goBtn");
  if(!goBtn) return;                                  // not the landing page

  const prog=$("#prog"), bar=prog?prog.querySelector("i"):null;
  const statusTxt=$("#statusTxt"), badge=$("#badge"), msg=$("#vqMsg");
  const inputs=[["i1","t1","f1"],["i2","t2","f2"],["i3","t3","f3"],["i4","t4","f4"]].map(([i,t,f])=>({input:$("#"+i),demo:$("#"+t),wrap:$("#"+f)}));
  const MAX_WAIT_MS=8*60*1000;
  let running=false, demoActive=true;

  /* ---------- small UI helpers ---------- */
  const setStatus=t=>{ statusTxt.textContent=t; badge.setAttribute("title",t); };
  const setProgress=p=>{ if(bar) bar.style.width=Math.max(0,Math.min(100,p))+"%"; };
  const showMsg=(t,kind)=>{ if(!t){ msg.hidden=true; msg.textContent=""; return; } msg.textContent=t; msg.className="vq-msg"+(kind==="info"?" info":""); msg.hidden=false; };
  const setBusy=b=>{
    goBtn.classList.toggle("busy",b); badge.classList.toggle("busy",b);
    inputs.forEach(x=>{x.input.disabled=b;});
    if(b) goBtn.textContent="Researching…";
  };

  /* ---------- the original "typing" intro, now cosmetic only (it never starts research) ---------- */
  const demo=[["t1","Aurelia Systems","f1"],["t2","linkedin.com/company/aurelia","f2"],["t3","Fri, 14 Nov · 11:00","f3"],["t4","Partnership call","f4"]];
  const stopDemo=()=>{
    if(!demoActive) return;
    demoActive=false;
    $$(".caret").forEach(c=>c.remove());
    inputs.forEach(x=>{ x.demo.textContent=""; });
    $$(".inp").forEach(b=>{ if(document.activeElement!==b.querySelector("input")) b.classList.remove("focus"); });
  };
  async function typeDemo(){
    for(const [id,text,box] of demo){
      if(!demoActive) return;
      $$(".inp").forEach(b=>b.classList.remove("focus"));
      $$(".caret").forEach(c=>c.remove());
      const el=$("#"+id), wrap=$("#"+box); wrap.classList.add("focus");
      el.textContent=""; const c=document.createElement("i"); c.className="caret"; wrap.appendChild(c);
      for(const ch of text){ if(!demoActive) return; el.textContent+=ch; if(!reduce) await sleep(34); }
      if(!reduce) await sleep(200);
    }
    if(!demoActive) return;
    $$(".caret").forEach(c=>c.remove());
    $$(".inp").forEach(b=>b.classList.remove("focus"));
  }

  /* real inputs: hide the demo text while the user is typing in a field */
  inputs.forEach(({input,wrap})=>{
    const sync=()=>wrap.classList.toggle("vq-active",document.activeElement===input||input.value!=="");
    input.addEventListener("focus",()=>{ stopDemo(); sync(); });
    input.addEventListener("input",sync);
    input.addEventListener("blur",sync);
    input.addEventListener("keydown",e=>{ if(e.key==="Enter"){ e.preventDefault(); start(); } });
  });

  /* ---------- polling ---------- */
  async function poll(fetcher,onTick){
    const t0=Date.now(); let fails=0;
    for(;;){
      if(Date.now()-t0>MAX_WAIT_MS) throw new VQApi.ApiError(0,"client_timeout","This is taking longer than expected. Please try again in a moment.");
      await sleep(Date.now()-t0>30000?2000:1100);
      try{
        const r=await fetcher();
        fails=0; onTick(r);
        if(r.status==="completed"||r.status==="failed") return r;
      }catch(e){
        if([401,404,422].includes(e.status)||++fails>=4) throw e;     // tolerate brief network blips
      }
    }
  }

  /* ---------- main flow ---------- */
  async function start(){
    if(running) return;                                              // no duplicate submissions
    showMsg("");
    const val=x=>x.input.value.trim();
    const name=val(inputs[0]);
    if(!name){
      stopDemo();
      setStatus("Enter a name to start");
      showMsg("Type the company or person you're meeting, then press Start Research.","error");
      inputs[0].input.focus();
      return;
    }
    const payload={name, url:val(inputs[1])||null, meeting_time:val(inputs[2])||null, purpose:val(inputs[3])||null, auto_brief:true};

    running=true; stopDemo(); setBusy(true); setProgress(0);
    VelQora.renderIdle();
    setStatus("Starting research…");
    try{
      const job=await VQApi.startResearch(payload);
      setProgress(job.progress||2);
      const done=await poll(()=>VQApi.getResearch(job.research_id),r=>{
        setStatus(r.message||"Researching…"); setProgress(r.progress||0);
      });
      if(done.status==="failed"){
        const e=done.error||{};
        throw new VQApi.ApiError(0,e.code||"failed",e.message||"Research failed. Please try again.");
      }
      if(!done.briefing_id) throw new VQApi.ApiError(0,"no_briefing","Research finished but no briefing was produced.");

      let b=await VQApi.getBriefing(done.briefing_id);
      if(b.status!=="completed") b=await poll(()=>VQApi.getBriefing(done.briefing_id),r=>setStatus(r.message||"Preparing your brief…"));
      if(b.status!=="completed"||!b.briefing) throw new VQApi.ApiError(0,"briefing_failed",(b.error&&b.error.message)||"The briefing could not be generated.");

      setProgress(100);
      setStatus("Brief ready ✓");
      await VelQora.reveal(VelQora.toView(b.briefing));
      afterBrief(b.briefing);
      goBtn.textContent="Run again ↻";
    }catch(e){
      console.error("[VelQora]",e);
      VelQora.renderIdle();
      setProgress(0);
      setStatus(e.code==="network"?"Server unreachable":"Couldn't complete research");
      showMsg(e.message||"Something went wrong. Please try again.","error");
      goBtn.textContent="Try again ↻";
    }finally{
      running=false; setBusy(false);
    }
  }

  /* surface honest notes: empty results, missing AI analysis, flagged content */
  function afterBrief(b){
    const notes=[...(b.warnings||[])];
    if(!b.sources.length) notes.unshift("No relevant sources were found. Check the spelling or add the company website.");
    else if(!b.recent_developments.length && !b.important_news.length) notes.unshift("No dated developments from the last 30 days were found.");
    if(notes.length) showMsg(notes.slice(0,2).join(" "),"info");
  }

  goBtn.addEventListener("click",start);

  /* ---------- boot ---------- */
  VelQora.renderIdle();                                   // skeleton, exactly as before
  setProgress(0);
  if(reduce){ demo.forEach(([id,t])=>{ $("#"+id).textContent=t; }); }
  else setTimeout(typeDemo,1700);
  VQApi.health().catch(e=>{
    if(e.code==="network") showMsg("The VelQora backend isn't reachable yet. Start it (see README), then reload this page.","error");
  });
})();
