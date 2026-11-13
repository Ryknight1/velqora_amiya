/* ============================================================
   VelQora — shared helpers + landing-page effects.
   The parallax / spotlight / scroll / nav code below is the original
   behaviour, unchanged except for null-guards so it can also load on
   the sign-in and briefing pages.
   ============================================================ */
document.documentElement.classList.add("js");

const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const reduce=matchMedia("(prefers-reduced-motion: reduce)").matches;
/* Everything that comes from the backend (including AI text) is escaped before it touches innerHTML. */
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const safeHref=u=>/^https?:\/\//i.test(String(u||""))?String(u):"#";

/* ---- 3D pointer parallax on the whole stage ---- */
const scene=$("#scene"),stage=$("#stage");
const fine=matchMedia("(min-width:641px)").matches && !reduce;
if(fine && scene && stage){
  scene.addEventListener("pointermove",e=>{
    const r=scene.getBoundingClientRect();
    const x=(e.clientX-r.left)/r.width-.5, y=(e.clientY-r.top)/r.height-.5;
    stage.style.setProperty("--ry",(-12+x*16).toFixed(2)+"deg");
    stage.style.setProperty("--rx",(4-y*12).toFixed(2)+"deg");
  });
  scene.addEventListener("pointerleave",()=>{stage.style.setProperty("--ry","-12deg");stage.style.setProperty("--rx","4deg");});

  /* per-card tilt + light glare (cards are re-rendered with new data, so delegate from the stage) */
  const tilt=e=>{
    const c=e.target.closest&&e.target.closest(".card"); if(!c) return;
    const r=c.getBoundingClientRect(), x=(e.clientX-r.left)/r.width, y=(e.clientY-r.top)/r.height;
    c.style.setProperty("--ty",((x-.5)*12).toFixed(1)+"deg");
    c.style.setProperty("--tx",((.5-y)*12).toFixed(1)+"deg");
    c.style.setProperty("--mx",(x*100).toFixed(1)+"%");
    c.style.setProperty("--my",(y*100).toFixed(1)+"%");
  };
  stage.addEventListener("pointermove",tilt);
  $$(".card").forEach(c=>c.addEventListener("pointerleave",()=>{c.style.setProperty("--tx","0deg");c.style.setProperty("--ty","0deg");}));
}
if(fine){
  /* magnetic buttons */
  $$(".mag").forEach(b=>{
    b.addEventListener("pointermove",e=>{
      const r=b.getBoundingClientRect();
      const dx=(e.clientX-(r.left+r.width/2))*.22, dy=(e.clientY-(r.top+r.height/2))*.3;
      b.style.translate=`${dx.toFixed(1)}px ${dy.toFixed(1)}px`;
    });
    b.addEventListener("pointerleave",()=>{b.style.translate="0 0";});
  });

  /* cursor spotlight */
  const spot=$("#spot");
  if(spot) addEventListener("pointermove",e=>{spot.style.setProperty("--sx",e.clientX+"px");spot.style.setProperty("--sy",e.clientY+"px");},{passive:true});
}

/* ---- Scroll: progress bar, nav state, depth parallax ---- */
const nav=$("#nav"),sbar=$("#sbar");
function onScroll(){
  if(nav) nav.classList.toggle("scrolled",scrollY>20);
  const max=document.documentElement.scrollHeight-innerHeight;
  if(sbar) sbar.style.setProperty("--p",max>0?(scrollY/max).toFixed(4):0);
  if(!reduce && scene) scene.style.setProperty("--scroll",scrollY);
}
addEventListener("scroll",onScroll,{passive:true}); onScroll();

/* ---- Reveal on scroll ---- */
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target)}}),{threshold:.15});
$$(".io").forEach(el=>io.observe(el));

/* ---- Mobile nav + active link ---- */
const burger=$("#burger"),links=$("#links");
if(burger && links){
  burger.addEventListener("click",()=>{burger.classList.toggle("open");links.classList.toggle("open");});
  links.querySelectorAll("a").forEach(a=>a.addEventListener("click",()=>{
    links.querySelectorAll("a").forEach(x=>x.classList.remove("active")); a.classList.add("active");
    burger.classList.remove("open"); links.classList.remove("open");
  }));
}
