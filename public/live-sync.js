/* AeroLeadAI GateKeeper live data synchronization.
 * Refreshes public, source-attributed evidence without rebuilding Vercel after
 * each GitHub Actions data commit. Does not create roof findings or write data.
 */
(()=>{'use strict';
const BASE='https://raw.githubusercontent.com/zaccboi8484/aero1/main/evidence/data/';
const INTERVAL=180000; // 3-minute browser refresh; scheduled GitHub crawls may run later.
const main=Boolean(document.getElementById('territorySelect'));
const scorecards=Boolean(document.getElementById('top20'));
if(!main&&!scorecards)return;
const panel=document.createElement('section');
panel.setAttribute('aria-label','Live source synchronization');
panel.style.cssText='display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin:12px 0;padding:10px 13px;border:1px solid rgba(93,164,182,.45);border-radius:12px;background:rgba(13,45,61,.90);color:#e6f8fc;font:12px/1.5 system-ui,sans-serif;box-shadow:0 8px 25px rgba(7,25,39,.16)';
const label=document.createElement('span');label.role='status';label.setAttribute('aria-live','polite');label.textContent='Live evidence: checking source publication…';label.style.cssText='flex:1;min-width:230px';
const refreshButton=document.createElement('button');refreshButton.type='button';refreshButton.textContent='↻ Refresh evidence';
refreshButton.style.cssText='border:1px solid #72aab4;border-radius:8px;background:#164a59;color:#fff;padding:8px 11px;cursor:pointer';
const a=document.createElement('a');a.href=main?'/roofing-scorecards.html':'/';
a.textContent=main?'Residential roofing cards ↗':'Main evidence dashboard ↗';
a.style.cssText='color:#a3eef2;text-decoration:underline;font-weight:700';
panel.append(label,refreshButton,a);
(document.querySelector('main')||document.body).prepend(panel);
let lastCursor=null,refreshing=false,lastDisplay=0;
function timeLabel(iso){
 const date=Date.parse(iso||'');
 if(!Number.isFinite(date))return 'unknown';
 return new Date(date).toLocaleString();
}
async function inspect(){
 const url=BASE+'fast_validation_cursor.json?audit='+Date.now();
 const r=await fetch(url,{cache:'no-store',headers:{Accept:'application/json'}});
 if(!r.ok)throw Error('Source index HTTP '+r.status);
 const j=await r.json();
 const instant=Date.parse(j.updated_at_utc||'');
 if(!Number.isFinite(instant))throw Error('Source index has no valid publication time');
 const ageMinutes=Math.max(0,Math.floor((Date.now()-instant)/60000));
 const state=ageMinutes>120?'SOURCE STALE':'SOURCE UPDATING';
 const cursor=j.updated_at_utc;
 return {cursor,ageMinutes,state};
}
async function refresh(force=false){
 if(refreshing||document.hidden)return;
 refreshing=true;
 refreshButton.disabled=true;
 try{
  const state=await inspect();
  const changed=lastCursor!==state.cursor;
  const overdue=Date.now()-lastDisplay>720000; // also refresh static permit/valuation sources.
  if(force||changed||overdue){
   if(main){
    if(typeof loadCandidates==='function')await loadCandidates();
    if(typeof loadReleaseTruth==='function')await loadReleaseTruth();
   }else if(scorecards&&typeof load==='function'){
    await load();
   }
   lastDisplay=Date.now();
  }
  lastCursor=state.cursor;
  label.textContent='GateKeeper '+state.state+' · Last source publish '+timeLabel(state.cursor)+' · '+state.ageMinutes+'m ago · '+(changed||force?'Cards refreshed':'No new publication')+'. Source fetches do not certify roof condition.';
 }catch(e){
  label.textContent='GateKeeper SOURCE CHECK FAILED · '+String(e.message||e).slice(0,100)+' · Existing evidence remains unverified.';
 }finally{
  refreshing=false;refreshButton.disabled=false;
 }
}
refreshButton.addEventListener('click',()=>refresh(true));
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>refresh(false),{once:true});
else refresh(false);
window.setInterval(()=>refresh(false),INTERVAL);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh(false)});
})();
