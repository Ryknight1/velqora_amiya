/* Persist research/briefing/presentation ids across pages (session + local recovery). */
const VQContext=(()=>{
  const KEY="vq_workflow";
  const HEX=/^[a-f0-9]{32}$/;
  function read(){
    try{return JSON.parse(sessionStorage.getItem(KEY)||localStorage.getItem(KEY)||"null");}catch(_){return null;}
  }
  function write(patch){
    const data=Object.assign({},read()||{},patch||{},{updated_at:Date.now()});
    try{sessionStorage.setItem(KEY,JSON.stringify(data));localStorage.setItem(KEY,JSON.stringify(data));}catch(_){}
    return data;
  }
  function clear(){
    try{sessionStorage.removeItem(KEY);localStorage.removeItem(KEY);}catch(_){}
  }
  function fromLocation(){
    const q=new URLSearchParams(location.search);
    const patch={};
    ["research_id","briefing_id","presentation_id"].forEach(k=>{
      const v=q.get(k); if(HEX.test(v||"")) patch[k]=v;
    });
    const entity=q.get("entity_name")||q.get("name");
    if(entity) patch.entity_name=entity.slice(0,120);
    if(Object.keys(patch).length) write(patch);
    return read();
  }
  function href(page){
    const c=read()||{};
    const [path, hash] = page.split("#");
    const [base, existingQuery] = path.split("?");
    const q=new URLSearchParams(existingQuery||"");
    if(c.research_id && !q.has("research_id")) q.set("research_id",c.research_id);
    if(c.briefing_id && !q.has("briefing_id")) q.set("briefing_id",c.briefing_id);
    if(c.presentation_id && /studio/.test(base) && !q.has("presentation_id")) q.set("presentation_id",c.presentation_id);
    const s=q.toString();
    const withQuery = s ? base + "?" + s : base;
    return hash ? withQuery + "#" + hash : withQuery;
  }
  function wireLinks(container){
    const root = container || document;
    root.querySelectorAll("a[href]").forEach(a=>{
      const h = a.getAttribute("href");
      if(h && !h.startsWith("#") && !h.startsWith("http://") && !h.startsWith("https://") && !h.startsWith("mailto:") && !h.includes("signin.html")){
        a.setAttribute("href", href(h));
      }
    });
  }
  return {read,write,clear,fromLocation,href,wireLinks,HEX};
})();
if(typeof VQContext!=="undefined"){
  VQContext.fromLocation();
  if(document.readyState==="loading"){
    document.addEventListener("DOMContentLoaded",()=>VQContext.wireLinks());
  } else {
    VQContext.wireLinks();
  }
}
