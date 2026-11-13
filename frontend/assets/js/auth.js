/* ============================================================
   VelQora auth — token storage + nav "Sign In / Sign Out" link.
   Prototype note: the token lives in localStorage; move to an httpOnly cookie before production.
   ============================================================ */
const VQAuth=(()=>{
  const KEY="vq_session";
  const read=()=>{try{return JSON.parse(localStorage.getItem(KEY)||"null");}catch(_){return null;}};
  const write=v=>{try{if(v)localStorage.setItem(KEY,JSON.stringify(v));else localStorage.removeItem(KEY);}catch(_){}};
  return {
    getToken(){const s=read();return s&&s.token&&(!s.exp||s.exp>Date.now())?s.token:null;},
    getUser(){const s=read();return s&&s.user?s.user:null;},
    isSignedIn(){return !!this.getToken();},
    setSession(resp){write({token:resp.access_token,user:resp.user,exp:Date.now()+resp.expires_in*1000});},
    signOut(){write(null);}
  };
})();

(function wireNav(){
  const link=document.getElementById("signinLink");
  if(!link||!VQAuth.isSignedIn()) return;
  link.textContent="Sign Out";
  link.setAttribute("href","#");
  link.addEventListener("click",e=>{e.preventDefault();VQAuth.signOut();location.reload();});
})();

/* ---------- sign-in / create-account page ---------- */
(function authPage(){
  const form=document.getElementById("authForm");
  if(!form) return;
  const $id=i=>document.getElementById(i);
  let mode="login";
  const copy={
    login:{title:"Welcome back",sub:"Sign in to keep your briefings with your account.",btn:"Sign In →",sw:"New to VelQora? ",swBtn:"Create an account",pw:"current-password"},
    register:{title:"Create your account",sub:"Free while we're in preview. Your password is stored hashed, never in plain text.",btn:"Create account →",sw:"Already have an account? ",swBtn:"Sign in",pw:"new-password"}
  };
  function setMode(m){
    mode=m; const c=copy[m];
    $id("authTitle").textContent=c.title; $id("authSub").textContent=c.sub; $id("authSubmit").textContent=c.btn;
    $id("authSwitchText").textContent=c.sw; $id("authToggle").textContent=c.swBtn;
    $id("nameField").hidden=(m==="login"); $id("aPass").setAttribute("autocomplete",c.pw); $id("authMsg").hidden=true;
  }
  $id("authToggle").addEventListener("click",()=>setMode(mode==="login"?"register":"login"));
  let busy=false;
  form.addEventListener("submit",async e=>{
    e.preventDefault(); if(busy) return;
    const msg=$id("authMsg"), btn=$id("authSubmit");
    const email=$id("aEmail").value.trim(), pass=$id("aPass").value, name=$id("aName").value.trim();
    const fail=t=>{msg.textContent=t;msg.className="vq-msg";msg.hidden=false;};
    if(!email||!pass) return fail("Enter your email and password.");
    if(mode==="register"&&pass.length<8) return fail("Use at least 8 characters for your password.");
    busy=true; btn.classList.add("busy"); msg.hidden=true;
    try{
      const resp=mode==="login"?await VQApi.login(email,pass):await VQApi.register(email,pass,name);
      VQAuth.setSession(resp);
      location.href="index.html";
    }catch(err){ fail(err.message||"Something went wrong."); }
    finally{ busy=false; btn.classList.remove("busy"); }
  });
  setMode("login");
})();
