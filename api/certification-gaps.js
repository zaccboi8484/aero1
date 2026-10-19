/* GateKeeper certification search: authenticated read-only view into published
 * source-backed evidence tasks. Does not approve a permit, roof claim or Mindex.
 */
import {authorized} from './auth.js';

const ROOT='https://raw.githubusercontent.com/zaccboi8484/aero1/main/evidence/data/';
const FILES=['certification_gap_summary.json','certification_gap_queue.json'];
let memo={until:0,summary:null,queue:null};
async function load(){
 if(memo.summary&&memo.queue&&Date.now()<memo.until)return memo;
 const fetched=await Promise.all(FILES.map(async name=>{
  const r=await fetch(ROOT+name,{cache:'no-store',signal:AbortSignal.timeout(13000)});
  if(!r.ok)throw Error(name+' not published (HTTP '+r.status+')');
  return r.json();
 }));
 const [summary,queue]=fetched;
 if(summary.version!=='GATEKEEPER_CERTIFICATION_GAP_V1'||queue.version!==summary.version||
    summary.original_residential_parcels!==60||summary.release_certified!==false||
    summary.full_property_certifications!==0||
    !Array.isArray(queue.tasks)||!Array.isArray(queue.per_property_truth)||
    queue.per_property_truth.length!==60||queue.tasks.length!==summary.task_count||
    queue.tasks.some(t=>t.completed===true||t.certification_approved===true)||
    new Set(queue.tasks.map(t=>t.task_id)).size!==queue.tasks.length){
   throw Error('GateKeeper evidence index integrity check failed');
 }
 memo={summary,queue,until:Date.now()+120000};return memo;
}
const number=(v,otherwise)=>Number.isInteger(Number(v))?Number(v):otherwise;
export default async function handler(req,res){
 res.setHeader('Cache-Control','private, no-store');
 res.setHeader('X-Content-Type-Options','nosniff');
 if(req.method!=='GET')return res.status(405).json({error:'GET required'});
 if(!process.env.AERO_ACCESS_PASSCODE||!process.env.AERO_SESSION_SECRET||!authorized(req))
  return res.status(401).json({error:'GateKeeper session required'});
 try{
  const {summary,queue}=await load();
  const limit=Math.max(1,Math.min(100,number(req.query?.limit,25)));
  const offset=Math.max(0,Math.min(2000,number(req.query?.offset,0)));
  const query=String(req.query?.q||'').toLowerCase().slice(0,90).trim();
  const kind=String(req.query?.kind||'').slice(0,70);
  const matches=queue.tasks.filter(t=>(!kind||t.kind===kind)&&(!query||
    (String(t.address)+' '+String(t.county_pin)+' '+String(t.source_record_id||'')+' '+String(t.task_id)).toLowerCase().includes(query)));
  const generated=Date.parse(summary.generated_at_utc||'');
  return res.status(200).json({
   status:'SOURCE_BACKED_RESEARCH_QUEUE_NOT_CERTIFICATION',
   summary,returned:matches.slice(offset,offset+limit).length,total_matches:matches.length,
   requested_limit:limit,offset,next_offset:offset+limit<matches.length?offset+limit:null,
   report_stale:!Number.isFinite(generated)||Date.now()-generated>48*3600*1000,
   records:matches.slice(offset,offset+limit)
  });
 }catch(e){
  return res.status(503).json({error:'GateKeeper certification index not ready; no records fabricated',
   detail:String(e.message||e).slice(0,200)});
 }
}
