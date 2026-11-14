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
  function fromLocation(){
    const q=new URLSearchParams(location.search);
    const patch={};
    ["research_id","briefing_id","presentation_id"].forEach(k=>{
      const v=q.get(k); if(HEX.test(v||"")) patch[k]=v;
    });
    if(Object.keys(patch).length) write(patch);
    return read();
  }
  function href(page){
    const c=read()||{};
    const q=new URLSearchParams();
    if(c.research_id) q.set("research_id",c.research_id);
    if(c.briefing_id) q.set("briefing_id",c.briefing_id);
    if(c.presentation_id && /studio/.test(page)) q.set("presentation_id",c.presentation_id);
    const s=q.toString();
    return s?page+"?"+s:page;
  }
  return {read,write,fromLocation,href,HEX};
})();
