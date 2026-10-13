/* Cook network dashboard. All probes run in the visitor's browser. */
(()=>{
"use strict";
const $=id=>document.getElementById(id);
const exitIps=new Map();
const visibleIps=new Set();
const routes={"/network":"network","/ip":"pool","/speed":"latency","/api":"api","/resources":"sources-card","/ports":"ports"};
let scanId=0,pingId=0;
function validIp(s){
  if(typeof s!=="string"||s.length>46||!s)return false;
  if(s.includes(":"))return /^[0-9a-f:.]+$/i.test(s)&&s.includes(":");
  const parts=s.split(".");
  return parts.length===4&&parts.every(n=>/^\d{1,3}$/.test(n)&&+n>=0&&+n<=255);
}
function maskIp(ip){
  if(!validIp(ip))return "暂不可用";
  if(ip.includes(":"))return ip.split(":").slice(0,2).join(":")+"::****";
  const p=ip.split(".");
  return p[0]+"."+p[1]+".***.***";
}
function setExit(route,ip,where,source){
  const id={"domestic":"net-domestic","foreign":"net-foreign","cloudflare":"net-cloudflare"}[route];
  const elem=$(id),region=$(id+"-region"),src=$(id+"-source");
  const button=document.querySelector('[data-view-ip="'+route+'"]');
  const card=elem.closest(".net-stat");
  const ok=validIp(ip);
  card.classList.toggle("net-unsupported",!ok);
  if(ok){exitIps.set(route,ip);elem.textContent=visibleIps.has(route)?ip:maskIp(ip);button.hidden=false;}
  else{exitIps.delete(route);elem.textContent="暂不可用";button.hidden=true;}
  region.textContent=where||"数据暂不可用";
  src.textContent=source||"检测接口暂不可用或被跨域策略拦截";
}
async function json(url,timeout=6500){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),timeout);
  try{
    const res=await fetch(url,{signal:controller.signal,cache:"no-store"});
    if(!res.ok)throw Error("HTTP "+res.status);
    return await res.json();
  }finally{clearTimeout(timer);}
}
function iconRequest(url,timeout=5600){
  return new Promise(resolve=>{
    const img=new Image();
    const started=performance.now();
    let done=false;
    const finish=state=>{
      if(done)return;done=true;
      clearTimeout(timer);img.onload=null;img.onerror=null;
      resolve({state,ms:Math.round(performance.now()-started)});
    };
    const timer=setTimeout(()=>finish("timeout"),timeout);
    img.onload=()=>finish("ok");
    img.onerror=()=>finish("error");
    img.src=url+(url.includes("?")?"&":"?")+"cook_probed="+Date.now();
  });
}
async function networkTest(){
  const sequence=++scanId;
  $("network-recheck").disabled=true;
  exitIps.clear();
  visibleIps.clear();
  for(const key of ["domestic","foreign","cloudflare"]){
    const id={"domestic":"net-domestic","foreign":"net-foreign","cloudflare":"net-cloudflare"}[key];
    $(id).textContent="检测中…";
    const button=document.querySelector('[data-view-ip="'+key+'"]');
    button.hidden=true;button.textContent="显示";
  }
  $("net-google").textContent="检测中…";
  $("net-google-region").textContent="正在请求 Google 图标资源";
  const responses=await Promise.allSettled([
    json("https://myip.ipip.net/json"),
    json("https://ipwho.is/"),
    json("https://speed.cloudflare.com/meta"),
    iconRequest("https://www.google.com/favicon.ico",6000)
  ]);
  if(sequence!==scanId)return;
  const [cn,global,cf,google]=responses.map(x=>x.status==="fulfilled"?x.value:null);
  const cd=cn?.ret==="ok"&&cn?.data?cn.data:null;
  setExit("domestic",cd?.ip,[...(cd?.location||[])].filter(Boolean).slice(0,3).join(" · "),
    cd?"来源：IPIP 国内网络查询服务":"国内接口不可用，可能被 CORS / 代理阻止");
  const geo=global?.success!==false?global:null;
  const foreignLocation=[geo?.country,geo?.region,geo?.connection?.isp].filter(Boolean).join(" · ");
  setExit("foreign",geo?.ip,foreignLocation,geo?"来源：ipwho.is（国际检测服务）":"国际检测服务暂不可用");
  const cloudflareLocation=[cf?.country,cf?.city,cf?.colo?"Colo "+cf.colo:null].filter(Boolean).join(" · ");
  setExit("cloudflare",cf?.clientIp,cloudflareLocation,
    cf?"来源：Cloudflare Speed Meta · "+(cf?.asOrganization||"ISP 未知"):"Cloudflare Meta 暂不可用");
  const good=google?.state==="ok";
  $("net-google").textContent=good?"可访问 · "+google.ms+"ms":google?.state==="timeout"?"连接超时":"无法加载";
  $("net-google-region").textContent=good?"Google 静态图标加载成功":"Google 资源不可用或被限制";
  $("net-google-source").textContent="通过 HTTPS 图标检测；无法读取 Google 出口 IP";
  $("net-google").closest(".net-stat").classList.toggle("net-error",!good);
  $("network-recheck").disabled=false;
}
for(const btn of document.querySelectorAll("[data-view-ip]")){
  btn.addEventListener("click",()=>{
    const type=btn.dataset.viewIp,ip=exitIps.get(type);
    if(!ip)return;
    if(visibleIps.has(type))visibleIps.delete(type);else visibleIps.add(type);
    const id={"domestic":"net-domestic","foreign":"net-foreign","cloudflare":"net-cloudflare"}[type];
    $(id).textContent=visibleIps.has(type)?ip:maskIp(ip);
    btn.textContent=visibleIps.has(type)?"隐藏":"显示";
    btn.setAttribute("aria-label",(visibleIps.has(type)?"隐藏":"显示")+"完整IP");
  });
}
const sites=[
  ["douyin","https://www.douyin.com/favicon.ico"],
  ["bilibili","https://www.bilibili.com/favicon.ico"],
  ["wechat","https://weixin.qq.com/favicon.ico"],
  ["taobao","https://www.taobao.com/favicon.ico"],
  ["github","https://github.com/favicon.ico"],
  ["jsdelivr","https://www.jsdelivr.com/favicon.ico"],
  ["cloudflare","https://www.cloudflare.com/favicon.ico"],
  ["youtube","https://www.youtube.com/favicon.ico"]
];
async function runPings(){
  const id=++pingId;
  $("ping-retry").disabled=true;
  $("ping-status").textContent="正在测试浏览器加载公开图标资源的耗时…";
  for(const [name] of sites){const e=$("ping-"+name);e.className="ping-time pending";e.textContent="检测中…";}
  const results=await Promise.all(sites.map(async ([name,url])=>{
    const r=await iconRequest(url);
    if(id!==pingId)return r;
    const elem=$("ping-"+name);
    elem.className=r.state==="ok"?"ping-time "+(r.ms<300?"rapid":r.ms<900?"normal":"slow"):"ping-time fail";
    elem.textContent=r.state==="ok"?r.ms+"ms":r.state==="timeout"?"超时":"无法加载";
    elem.title=r.state==="ok"?"浏览器加载图标资源耗时":"此资源可能被拦截、禁用盗链或返回非图片内容";
    return r;
  }));
  if(id!==pingId)return;
  const ok=results.filter(x=>x.state==="ok").length;
  $("ping-status").textContent="完成 "+ok+"/"+sites.length+" 项 · 这是资源请求时间，不等同 TCP Ping 或网站首屏性能。";
  $("ping-retry").disabled=false;
}
function applyTheme(theme){
  document.documentElement.dataset.theme=theme;
  $("theme-icon").textContent=theme==="dark"?"☀":"☾";
  $("theme-toggle").setAttribute("aria-label",theme==="dark"?"切换浅色模式":"切换深色模式");
}
try{applyTheme(localStorage.getItem("cook-theme")==="dark"?"dark":"light");}catch(e){applyTheme("light");}
$("theme-toggle").addEventListener("click",()=>{
  const theme=document.documentElement.dataset.theme==="dark"?"light":"dark";
  applyTheme(theme);
  try{localStorage.setItem("cook-theme",theme);}catch(e){}
});
function resolveRoute(){
  const path=location.hash.slice(1);
  if(!routes[path])return;
  const target=$(routes[path]);
  if(!target)return;
  for(const link of document.querySelectorAll(".site-links a"))link.classList.toggle("current",link.getAttribute("href")==="#"+path);
  requestAnimationFrame(()=>target.scrollIntoView({behavior:"smooth",block:"start"}));
}
window.addEventListener("hashchange",resolveRoute);
if(routes[location.hash.slice(1)])setTimeout(resolveRoute,0);
$("network-recheck").addEventListener("click",networkTest);
$("ping-retry").addEventListener("click",runPings);
networkTest();
runPings();
})();