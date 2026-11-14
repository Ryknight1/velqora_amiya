/* ============================================================
   VelQora API client — the ONLY place the frontend talks to the backend.
   No secrets live here: Tavily / Bifrost keys stay on the server.
   Override the backend address with:  <script>window.VELQORA_API_BASE="https://api.example.com"</script>
   ============================================================ */
const VQApi=(()=>{
  const cfg=window.VELQORA_API_BASE;
  const local=location.hostname==="localhost"||location.hostname==="127.0.0.1";
  /* same-origin when FastAPI serves the pages (port 8000 / production); otherwise the local dev backend */
  const base=(typeof cfg==="string"?cfg:(local&&location.port!=="8000"?"http://localhost:8000":"")).replace(/\/$/,"");

  class ApiError extends Error{
    constructor(status,code,message,details){super(message);this.name="ApiError";this.status=status;this.code=code;this.details=details;}
  }

  async function request(path,{method="GET",body,timeout=30000,auth=true,signal}={}){
    const ctrl=new AbortController();
    const timer=setTimeout(()=>ctrl.abort(),timeout);
    if(signal) signal.addEventListener("abort",()=>ctrl.abort(),{once:true});
    const headers={Accept:"application/json"};
    if(body!==undefined) headers["Content-Type"]="application/json";
    const token=auth&&typeof VQAuth!=="undefined"?VQAuth.getToken():null;
    if(token) headers.Authorization="Bearer "+token;
    let res;
    try{
      res=await fetch(base+path,{method,headers,body:body!==undefined?JSON.stringify(body):undefined,signal:ctrl.signal,credentials:"omit"});
    }catch(e){
      clearTimeout(timer);
      if(e&&e.name==="AbortError") throw new ApiError(0,"timeout","The server took too long to respond.");
      throw new ApiError(0,"network","Can't reach the VelQora server. Make sure the backend is running.");
    }
    clearTimeout(timer);
    let data=null; try{data=await res.json();}catch(_){}
    if(!res.ok){
      const err=data&&data.error;
      throw new ApiError(res.status,(err&&err.code)||"http_error",(err&&err.message)||`Request failed (${res.status}).`,err&&err.details);
    }
    return data;
  }

  const enc=encodeURIComponent;
  return {
    ApiError, base, request,
    health:()=>request("/api/health",{timeout:6000,auth:false}),
    services:(deep=false)=>request("/api/health/services"+(deep?"?deep=true":""),{timeout:45000}),
    startResearch:payload=>request("/api/research",{method:"POST",body:payload}),
    getResearch:(id,opts)=>request("/api/research/"+enc(id),opts),
    generateBriefing:(researchId,force=false)=>request("/api/briefing/generate",{method:"POST",body:{research_id:researchId,force}}),
    getBriefing:(id,opts)=>request("/api/briefing/"+enc(id),opts),
    register:(email,password,name)=>request("/api/auth/register",{method:"POST",body:{email,password,name:name||null},auth:false}),
    login:(email,password)=>request("/api/auth/login",{method:"POST",body:{email,password},auth:false}),
    me:()=>request("/api/auth/me"),
    createPresentation:payload=>request("/api/presentation/create",{method:"POST",body:payload,timeout:60000}),
    presentationChat:payload=>request("/api/presentation/chat",{method:"POST",body:payload,timeout:60000}),
    getPresentation:(id,opts)=>request("/api/presentation/"+enc(id),opts),
    updatePresentation:(id,presentation,summary=null,save_version=false)=>request("/api/presentation/"+enc(id),{method:"PUT",body:{presentation,summary,save_version}}),
    getPresentationVersions:(id,opts)=>request("/api/presentation/"+enc(id)+"/versions",opts),
    getPresentationHistory:(id,opts)=>request("/api/presentation/"+enc(id)+"/history",opts),
    restorePresentationVersion:(id,versionNum)=>request("/api/presentation/"+enc(id)+"/restore/"+enc(versionNum),{method:"POST"}),
    exportPresentation:(id,format="pptx",theme_override=null)=>request("/api/presentation/"+enc(id)+"/export",{method:"POST",body:{format,theme_override},timeout:60000}),
    getPresentationDownloadUrl:(id,exportId=null)=>base+"/api/presentation/"+enc(id)+"/download"+(exportId?"?export_id="+enc(exportId):"")
  };
})();
