/* Shared application chrome: logo, links, account, mobile menu. */
const VQNav=(()=>{
  const LOGO=`<svg class="logo" viewBox="0 0 40 40" aria-hidden="true">
      <defs>
        <linearGradient id="vqBg" x1="0" y1="0" x2=".55" y2="1"><stop offset="0" stop-color="#22355f"/><stop offset="1" stop-color="#111a38"/></linearGradient>
        <radialGradient id="vqGlow" cx=".82" cy=".08" r=".75"><stop offset="0" stop-color="#FF5858" stop-opacity=".6"/><stop offset="1" stop-color="#FF5858" stop-opacity="0"/></radialGradient>
        <linearGradient id="vqCoral" x1=".9" y1="0" x2=".2" y2="1"><stop offset="0" stop-color="#ff8f7f"/><stop offset="1" stop-color="#FF5858"/></linearGradient>
        <linearGradient id="vqCream" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FAF6EF"/><stop offset="1" stop-color="#F4EDE0"/></linearGradient>
      </defs>
      <rect x=".8" y=".8" width="38.4" height="38.4" rx="11.5" fill="url(#vqBg)"/>
      <rect x=".8" y=".8" width="38.4" height="38.4" rx="11.5" fill="url(#vqGlow)"/>
      <rect x=".8" y=".8" width="38.4" height="38.4" rx="11.5" fill="none" stroke="#fff" stroke-opacity=".2" stroke-width="1.2"/>
      <circle class="ring" cx="20" cy="20" r="15.6" fill="none" stroke="#F4EDE0" stroke-opacity=".3" stroke-width=".75" stroke-dasharray="1.5 2.3" stroke-linecap="round"/>
      <path d="M8.2 17.8 15.2 30.4" stroke="#3e4c6d" stroke-width="4.4" stroke-linecap="round" fill="none" opacity=".9"/>
      <path d="M26.6 12.4 18.4 25.8" stroke="#fff" stroke-opacity=".16" stroke-width="4.4" stroke-linecap="round" fill="none"/>
      <path class="st a" pathLength="1" d="M10.6 15 18 28" stroke="url(#vqCream)" stroke-width="4.2" stroke-linecap="round" fill="none"/>
      <path class="st b" pathLength="1" d="M18 28 29.8 10.5" stroke="url(#vqCoral)" stroke-width="4.4" stroke-linecap="round" fill="none"/>
      <circle class="pop" style="animation-delay:.9s" cx="10.6" cy="15" r="1.35" fill="#101A30"/>
      <circle class="pop" style="animation-delay:1.1s" cx="29.8" cy="10.5" r="1.2" fill="#FAF6EF"/>
      <circle class="pop" style="animation-delay:1.2s" cx="8" cy="9.8" r=".9" fill="#b9bccb" opacity=".8"/>
      <circle class="halo2" cx="32.2" cy="30" r="3.4" fill="#FF5858" opacity=".28"/>
      <circle class="pop" style="animation-delay:1.3s" cx="32.2" cy="30" r="1.9" fill="#FF5858"/>
    </svg>`;
  const ITEMS=[
    {href:"index.html",label:"Home",key:"index"},
    {href:"research.html",label:"New Research",key:"research"},
    {href:"intelligence.html",label:"Intelligence",key:"intelligence"},
    {href:"meeting.html",label:"Meeting Prep",key:"meeting"},
    {href:"studio.html",label:"Presentation Studio",key:"studio"}
  ];
  function pageKey(){
    const f=(location.pathname.split("/").pop()||"index.html").toLowerCase();
    if(f===""||f==="/"||f==="index.html") return "index";
    return f.replace(".html","");
  }
  function mount(nav){
    if(!nav) return;
    const key=pageKey();
    const link=(item)=>{
      const url=typeof VQContext!=="undefined"?VQContext.href(item.href):item.href;
      const active=item.key===key?" class=\"active\" aria-current=\"page\"":"";
      return `<li><a href="${url}"${active}>${item.label}</a></li>`;
    };
    nav.innerHTML=`
      <a href="${typeof VQContext!=="undefined"?VQContext.href("index.html"):"index.html"}" class="brand" aria-label="VelQora home">${LOGO}VelQora</a>
      <ul class="links" id="links">
        ${ITEMS.map(link).join("")}
        <li class="mobile-only-auth"><a href="signin.html" id="mobileAuthLink">Sign In</a></li>
      </ul>
      <div class="nav-r">
        <span class="user-chip" id="userChip" hidden></span>
        <a href="signin.html" class="signin" id="signinLink">Sign In</a>
        <a href="${typeof VQContext!=="undefined"?VQContext.href("research.html"):"research.html"}" class="btn btn-coral mag">Start Research</a>
        <button class="burger" id="burger" type="button" aria-label="Menu" aria-expanded="false"><i></i><i></i><i></i></button>
      </div>`;
    const burger=nav.querySelector("#burger"), links=nav.querySelector("#links");
    if(burger&&links){
      burger.addEventListener("click",()=>{
        const open=links.classList.toggle("open");
        burger.classList.toggle("open",open);
        burger.setAttribute("aria-expanded",open?"true":"false");
      });
      links.querySelectorAll("a").forEach(a=>a.addEventListener("click",()=>{
        links.classList.remove("open"); burger.classList.remove("open");
        burger.setAttribute("aria-expanded","false");
      }));
    }
  }
  return {mount,pageKey};
})();
if(typeof VQContext!=="undefined") VQContext.fromLocation();
VQNav.mount(document.getElementById("nav"));
