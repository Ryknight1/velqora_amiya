/* Dedicated research workspace: POST /api/research, poll status, persist ids, continue to intelligence. */
(function(){
  const form=$("#researchForm");
  const goBtn=$("#goBtn");
  if(!form||!goBtn) return;

  const prog=$("#prog"), bar=prog?prog.querySelector("i"):null;
  const msg=$("#vqMsg"), stageList=$("#stageList");
  const KNOWN=["queued","validating","searching","processing","date_validation","analyzing","verifying","preparing","completed","failed"];
  const MAX_WAIT_MS=8*60*1000;
  let running=false;

  const showMsg=(t,kind)=>{ if(!t){ msg.hidden=true; msg.textContent=""; return; } msg.textContent=t; msg.className="vq-msg"+(kind==="info"?" info":""); msg.hidden=false; };
  const setProgress=p=>{ if(!prog||!bar) return; prog.hidden=false; bar.style.width=Math.max(0,Math.min(100,Number(p)||0))+"%"; };
  const setBusy=b=>{
    running=b; goBtn.classList.toggle("busy",b); goBtn.disabled=b;
    form.querySelectorAll("input,select").forEach(el=>el.disabled=b);
    goBtn.textContent=b?"Researching…":"Start Research";
  };
  function renderStages(stage){
    if(!stageList) return;
    stageList.replaceChildren();
    KNOWN.filter(s=>s!=="failed"&&s!=="queued").forEach(s=>{
      const el=document.createElement("span");
      el.className="stage-pill"+(s===stage?" on":"");
      el.textContent=s.replace(/_/g," ");
      stageList.appendChild(el);
    });
  }

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
        if([401,404,422].includes(e.status)||++fails>=4) throw e;
      }
    }
  }

  async function start(e){
    if(e) e.preventDefault();
    if(running) return;
    showMsg("");
    const name=$("#rName").value.trim();
    if(!name){
      showMsg("Enter the company or person you are meeting.","error");
      $("#rName").focus();
      return;
    }
    const payload={
      name,
      url:$("#rUrl").value.trim()||null,
      meeting_time:$("#rTime").value.trim()||null,
      purpose:$("#rPurpose").value.trim()||null,
      entity_type:$("#rType").value||"auto",
      auto_brief:true
    };
    setBusy(true); setProgress(0); renderStages("validating");
    try{
      const job=await VQApi.startResearch(payload);
      VQContext.write({research_id:job.research_id, briefing_id:job.briefing_id||null, entity_name:name});
      setProgress(job.progress||2);
      renderStages(job.stage||"searching");
      showMsg(job.message||"Research started…","info");
      const done=await poll(()=>VQApi.getResearch(job.research_id),r=>{
        showMsg(r.message||"Researching…","info");
        setProgress(r.progress||0);
        renderStages(r.stage);
        if(r.briefing_id) VQContext.write({research_id:r.research_id, briefing_id:r.briefing_id});
      });
      if(done.status==="failed"){
        const err=done.error||{};
        throw new VQApi.ApiError(0,err.code||"failed",err.message||"Research failed. Please try again.");
      }
      let briefingId=done.briefing_id;
      if(!briefingId){
        const gen=await VQApi.generateBriefing(done.research_id,false);
        briefingId=gen.briefing_id;
      }
      let b=await VQApi.getBriefing(briefingId);
      if(b.status!=="completed") b=await poll(()=>VQApi.getBriefing(briefingId),r=>{
        showMsg(r.message||"Preparing your brief…","info");
        setProgress(r.progress||0);
        renderStages(r.stage||"preparing");
      });
      if(b.status!=="completed"||!b.briefing) throw new VQApi.ApiError(0,"briefing_failed",(b.error&&b.error.message)||"The briefing could not be generated.");
      VQContext.write({research_id:done.research_id, briefing_id:b.briefing_id, entity_name:(b.briefing.entity&&b.briefing.entity.name)||name});
      setProgress(100); renderStages("completed");
      location.href=VQContext.href("intelligence.html");
    }catch(err){
      console.error("[VelQora]",err);
      showMsg(err.message||"Something went wrong. Please try again.","error");
      goBtn.textContent="Try again";
    }finally{
      setBusy(false);
    }
  }

  form.addEventListener("submit",start);

  const ctx=VQContext.read();
  if(ctx&&ctx.research_id){
    VQApi.getResearch(ctx.research_id).then(r=>{
      if(r.status==="running"||r.status==="queued"){
        showMsg(r.message||"A research job is still running…","info");
        start.resume=true;
      }
    }).catch(()=>{});
  }
  VQApi.health().catch(e=>{
    if(e.code==="network") showMsg("The VelQora backend isn't reachable yet. Start it (see README), then reload this page.","error");
  });
  const next=$("#nextIntel"); if(next) next.setAttribute("href",VQContext.href("intelligence.html"));
})();
