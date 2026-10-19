// AeroLeadAI / GateKeeper live production smoke check.
// Tests live HTTP behavior. Never invents permits, leaks credentials or certifies roof condition.
import assert from 'node:assert/strict';

const base=(process.env.AERO_BASE_URL||'https://aeroleadaigithubreadyv03.vercel.app').replace(/\/$/,'');
const cases=[
  {path:'/',code:200,match:/AeroLeadAI|Kings Wood/i,description:'main residential property interface'},
  {path:'/roofing-scorecards.html',code:200,match:/Residential Roofing Scorecards/i,description:'integrated original-60 scorecard UI'},
  {path:'/certification-gaps.html',code:200,match:/Certification Search Engine/,description:'source-directed GateKeeper certification queue UI'},
  {path:'/api/certification-gaps',code:401,match:/GateKeeper session required/,description:'certification research queue protected from unauthenticated access'},
  {path:'/live-sync.js',code:200,match:/source_health_public[.]json/,description:'deployed source heartbeat and automatic browser evidence refresh'},
  {path:'/',code:200,match:/src="[/]live-sync[.]js" defer/,description:'main dashboard linked to active refresh engine'},
  {path:'/roofing-scorecards.html',code:200,match:/src="[/]live-sync[.]js" defer/,description:'residential scorecards linked to active refresh engine'},
  {path:'/api/auth',code:200,match:/"authorized"\s*:\s*false/,description:'existing access-control health'},
  {path:'/api/roofing-scorecards?limit=20',code:401,match:/GateKeeper session required/,description:'scorecards protected from unauthenticated access'},
];
let failed=0;
for(const item of cases){
 const url=base+item.path;
 try{
  const response=await fetch(url,{redirect:'manual',headers:{Accept:'text/html,application/json'},signal:AbortSignal.timeout(15000)});
  const body=await response.text();
  const ok=response.status===item.code&&item.match.test(body);
  const protection=/Vercel Authentication|Log in to Vercel|Deployment Protection|Authentication Required/i.test(body);
  console.log(JSON.stringify({path:item.path,description:item.description,status:response.status,expected:item.code,passed:ok,vercel_protection_page:protection,body_size:body.length,redirect:response.headers.get('location')||null}));
  if(!ok)failed++;
 }catch(e){
  failed++;console.log(JSON.stringify({path:item.path,passed:false,error:String(e.message||e)}));
 }
}
assert.equal(failed,0,'Production is not passing all required GateKeeper HTTP gates');
console.log('GateKeeper live HTTP smoke: PASSED. This does not certify real-world property condition, image rights, or the Supabase audit ledger.');
