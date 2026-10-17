/* LuckyG GateKeeper Core v1 — zero-cost, offline, local-first retrieval.
 * This is NOT an LLM. It never claims unseen live searches or verified inspections.
 * No external keys, storage services or telemetry.
 */
(()=>{'use strict';
const KEY='aeroleadai_luckyg_memory_v1',VERSION=1;
const SEED=[
 {id:'architecture',title:'AeroLeadAI architecture',body:'AeroLeadAI uses official parcel GIS candidates, source-specific acquisition adapters, a review coordinator, GateKeeper provenance rules, and Mindex opportunity scoring. Supabase audit writes are not connected in the current deployment.',tags:['gatekeeper','architecture','pipeline','engine'],source:'Project architecture',status:'PROJECT_DOCUMENTED'},
 {id:'permits',title:'Eagan building permits',body:'City of Eagan is the primary permit authority for incorporated Eagan properties. Source searches and permit exports need address/parcel matching and human review. An absent permit match does not prove no permit exists.',tags:['permit','roof','replacement','building','eagan'],source:'https://eagan.onlama.com/Search.aspx',status:'SOURCE_CATALOG'},
 {id:'parcels',title:'Kings Wood parcel candidates',body:'The official GIS collector previously exported up to 60 Kings Wood street/plat candidates. Candidate membership and condition are not verified; check the current register for actual loaded count.',tags:['property','parcel','60','kings','wood','address'],source:'https://github.com/zaccboi8484/aero1/blob/main/evidence/data/kingswood_parcel_candidates.csv',status:'SOURCE_CATALOG'},
 {id:'imagery',title:'Images and Street View',body:'Google Street View is an outbound Google Maps link only. Property imagery must come from authorized Dakota County aerial sources or actual user-supplied photos, with source, capture date and review status. No Google imagery is stored in AeroLeadAI.',tags:['street','view','google','aerial','imagery','photo','camera'],source:'https://gis.co.dakota.mn.us/ObliqueViewer/',status:'PROJECT_POLICY'},
 {id:'mindex',title:'Mindex opportunity scoring',body:'Mindex is a proposed 0–100 business opportunity ranking using reviewed roof-age, storm, permits, property and imagery evidence. Property valuation is related but distinct. No score may be invented from a parcel ID, Street View link or missing data. Current unreviewed parcels are Not scored.',tags:['mindex','score','value','ranking','opportunity','lead'],source:'Project scoring policy',status:'PROJECT_POLICY'},
 {id:'security',title:'Human review and evidence',body:'LuckyG can log human notes and review recommendations, but personal notes are not official evidence. A human override must be authenticated, justified, audited and may not certify missing evidence.',tags:['human','override','verification','review','evidence','audit'],source:'GateKeeper project policy',status:'PROJECT_POLICY'},
 {id:'memory',title:'Local-first memory',body:'LuckyG memory is stored only in this browser and can be manually edited, imported or exported as JSON. It is free and offline after the page loads. It does not automatically synchronize across devices or retrain a model.',tags:['memory','save','remember','upload','import','export','free','offline'],source:'LuckyG core implementation',status:'SYSTEM_CAPABILITY'}
];
const norm=s=>String(s||'').toLowerCase().replace(/[^a-z0-9 ]/g,' ').replace(/\s+/g,' ').trim();
const stop=new Set('what is are can you me about the tell how which where why does have do my to for a an and of in with it we from this that on i has did'.split(' '));
function tokens(s){return norm(s).split(' ').filter(w=>w.length>2&&!stop.has(w))}
function read(){try{const v=JSON.parse(localStorage.getItem(KEY)||'{}');return Array.isArray(v.entries)?v:{version:VERSION,entries:[],history:[]}}catch{return {version:VERSION,entries:[],history:[]}}}
function save(m){localStorage.setItem(KEY,JSON.stringify({version:VERSION,entries:m.entries.slice(-300),history:(m.history||[]).slice(-120)}))}
function entries(){return [...SEED,...read().entries]}
function remember(title,body,source='User note'){title=String(title||'').trim();body=String(body||'').trim();if(!title||!body||body.length>4000)throw Error('Enter a title and a note under 4,000 characters');const m=read();m.entries.push({id:'note-'+Date.now()+'-'+Math.random().toString(36).slice(2,7),title,body,tags:tokens(title+' '+body).slice(0,30),source:String(source||'User note'),status:'USER_NOTE_UNVERIFIED',added_at:new Date().toISOString()});save(m);return m.entries.length}
function exportMemory(){return JSON.stringify({...read(),exported_at:new Date().toISOString(),format:'LuckyG Local Memory',version:VERSION},null,2)}
function importMemory(text){const x=JSON.parse(text);if(!Array.isArray(x.entries)||x.entries.length>300)throw Error('Invalid memory file or more than 300 entries');const safe=x.entries.map(p=>({id:String(p.id||'imported-'+Math.random()).slice(0,100),title:String(p.title||'').slice(0,160),body:String(p.body||'').slice(0,4000),tags:tokens(String(p.title||'')+' '+String(p.body||'')).slice(0,30),source:String(p.source||'Imported note').slice(0,240),status:'USER_NOTE_UNVERIFIED'})).filter(p=>p.title&&p.body);const m=read();const ids=new Set(m.entries.map(e=>e.id));for(const r of safe)if(!ids.has(r.id)){m.entries.push(r);ids.add(r.id)}save(m);return safe.length}
function lookup(question){const q=tokens(question);return entries().map(item=>{const title=new Set(tokens(item.title));const tag=new Set((item.tags||[]).map(norm));const body=norm(item.body);let points=0;for(const w of q){if(title.has(w))points+=5;if(tag.has(w))points+=3;if(body.includes(w))points+=1}return {item,points}}).filter(v=>v.points>0).sort((a,b)=>b.points-a.points).slice(0,3)}
function answer(question,context={}){const q=norm(question);const records=Array.isArray(context.records)?context.records:[];const matched=lookup(question);let response='';
if(/how many|count|number of parcels|properties collected/.test(q)){response='The current property register contains '+records.length+' loaded parcel candidate(s). These are not certified territory-membership or inspection findings. '}
if(/permit/.test(q)){const p=Array.isArray(context.permitReview)?context.permitReview:[];response+='The app currently has '+p.length+' permit match record(s) awaiting review in its loaded feed. This is not a complete search across municipal history. '}
if(/hottest|replace now|damage alert|most damage/.test(q)){response+='No verified damage or REPLACE NOW alerts can be established from the loaded candidate register. '}
if(/assessed|valuation|value retrieved|values retrieved|property values/.test(q)){
 const arr=Array.isArray(context.valuations)?context.valuations:[];
 const verified=arr.filter(x=>x?.valuation?.gatekeeper==='SOURCE_RECORDED').length;
 response+='AeroLeadAI currently has '+verified+' city GIS source-recorded property valuations from '+arr.length+' loaded records. These are not independent appraisals; the assessment year and reviewer approval are still missing. ';
}
if(/progress|verified|audit|completion|blocked|search status/.test(q)){
 const rows=Array.isArray(context.progress)?context.progress:[];
 const identities=rows.filter(x=>x.identity_status==='OFFICIAL_GIS_SOURCE_CONFIRMED').length;
 const complete=rows.filter(x=>x.completion==='COMPLETE').length;
 const waiting=rows.filter(x=>(x.checks||[]).some(c=>c.search_id==='permit'&&c.status==='SOURCE_ACCESS_BLOCKED')).length;
 response+='AeroLeadAI search audit: '+identities+' official GIS identity records confirmed; '+complete+' fully reviewed property investigations; '+waiting+' permit searches have source-access blocks. Identity confirmation is not a roof, damage or permit verification. ';
}
if(/storm|weather|noaa|alert/.test(q)){
 const alerts=Array.isArray(context.activeAlerts)?context.activeAlerts:[];
 response+='NOAA currently lists '+alerts.length+' area alert(s) in the imported Eagan-area feed. '+alerts.map(x=>String(x.event||'Unspecified alert')).slice(0,4).join(', ')+'. Regional weather alerts are not proof of an individual property being damaged. ';
}

if(!response&&matched.length){response+=matched.map(v=>v.item.title+': '+v.item.body+(v.item.status==='USER_NOTE_UNVERIFIED'?' [Personal note — unverified]':'')+(v.item.source?.startsWith('https://')?' Source: '+v.item.source:'')).join('\n\n');}
if(!response){response='I do not have a supported answer in the current AeroLeadAI evidence register or saved LuckyG memory. Add a dated, sourced knowledge entry using “Add knowledge,” or retrieve an official record and import it. I will not invent findings.'}
const m=read();m.history.push({question:String(question).slice(0,300),at:new Date().toISOString(),match_ids:matched.map(x=>x.item.id)});try{save(m)}catch{}
return response.trim()}
window.LuckyGCore=Object.freeze({answer,remember,entries,exportMemory,importMemory,stats:()=>({saved:read().entries.length,interactions:(read().history||[]).length})});
})();
