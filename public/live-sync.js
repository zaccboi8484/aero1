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
 let source=null,stamp=null,portal='NOT_REPORTED',checked=null,images=null;
 const r=await fetch(BASE+'source_health_public.json?audit='+Date.now(),{cache:'no-store',headers:{Accept:'application/json'}});
 if(r.ok){
  const j=await r.json();
  if(j.format!=='GATEKEEPER_SOURCE_HEARTBEAT_V1'||!j.source_data_present)throw Error('Source heartbeat invalid');
  stamp=j.source_report_run_utc;
  portal=j.municipal_portal_status||'NOT_REPORTED';
  checked=j.counts?.parcels_checked_last_run??null;
  images=j.counts?.government_jpeg_response_records??null;
  source='heartbeat';
 }else if(r.status===404){
  // During the first collector run after upgrade the previous cursor remains valid.
  const old=await fetch(BASE+'fast_validation_cursor.json?audit='+Date.now(),{cache:'no-store'});
  if(!old.ok)throw Error('Source index HTTP '+old.status);
  const j=await old.json();
  stamp=j.updated_at_utc;
  source='cursor';
 }else throw Error('GateKeeper source heartbeat HTTP '+r.status);
 const instant=Date.parse(stamp||'');
 if(!Number.isFinite(instant))throw Error('Source index has no valid publication time');
 const ageMinutes=Math.max(0,Math.floor((Date.now()-instant)/60000));
 const state=ageMinutes>120?'SOURCE STALE':'SOURCE CHECK ACTIVE';
 return {cursor:stamp,ageMinutes,state,portal,checked,images,source};
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
  label.textContent='GateKeeper '+state.state+' · Last source run '+timeLabel(state.cursor)+' · '+state.ageMinutes+'m ago'+(state.checked===null?'':' · '+state.checked+' parcels checked this run')+(state.images===null?'':' · '+state.images+' government WMS JPEG hashes')+(state.portal==='PUBLIC_SOURCE_UNAVAILABLE'?' · City permit portal BLOCKED':state.portal==='NOT_REPORTED'?'':' · City permit portal '+state.portal)+' · '+(changed||force?'Evidence reloaded':'No new source run')+'. Reported checks do not certify permits or roof condition.';
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
