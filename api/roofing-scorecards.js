/* Read-only, evidence-backed roofing scorecard feed for original 60 residences.
 * No new property rows, automated damage verdicts, or fabricated permits.
 * Source joins are by original parcel object ID and county PIN.
 */
import {authorized} from './auth.js';

const BASE='https://raw.githubusercontent.com/zaccboi8484/aero1/main/evidence/data/';
const FILES={
 parcels:'kingswood_parcel_candidates.csv',
 permits:'municipal_permit_export_audit.json',
 roofing:'roof_evidence_scores.json',
 valuation:'live_property_enrichment.json',
 imagery:'fast_validation_report.json'
};
let memory={until:0,value:null};
function csv(text){
 const rows=[];let cells=[],cell='',quoted=false;
 for(let i=0;i<text.length;i++){
  const ch=text[i];
  if(ch==='"'&&quoted&&text[i+1]==='"'){cell+='"';i++;continue}
  if(ch==='"'){quoted=!quoted;continue}
  if(ch===','&&!quoted){cells.push(cell);cell='';continue}
  if((ch==='\n'||ch==='\r')&&!quoted){
   if(ch==='\r'&&text[i+1]==='\n')i++;
   cells.push(cell);if(cells.some(x=>x.length))rows.push(cells);
   cells=[];cell='';continue
  }
  cell+=ch;
 }
 if(quoted)throw Error('CSV quotation unclosed');
 if(cell||cells.length){cells.push(cell);rows.push(cells)}
 const [headers,...body]=rows;
 if(!headers)throw Error('Missing parcel CSV headers');
 return body.map(line=>Object.fromEntries(headers.map((name,index)=>[name,line[index]??''])));
}
function mapUnique(list,label){
 const map=new Map();
 for(const row of list){
  const key=String(row.parcel_objectid||'');
  if(!key||map.has(key))throw Error('Duplicate or missing '+label+' parcel ID: '+key);
  map.set(key,row);
 }
 return map;
}
const n=v=>Number.isFinite(Number(v))&&v!==null&&v!==''?Number(v):null;
const sha=s=>/^[a-f0-9]{64}$/i.test(String(s||''));
export function assemble({parcels,permits,roofing,valuation,imagery}){
 const originals=csv(parcels);
 if(originals.length!==60)throw Error('Original residential 60 inventory changed; requires GateKeeper review');
 const pinSet=new Set();
 const ids=new Set();
 for(const p of originals){
  if(!p.parcel_objectid||!p.county_pin||!p.address||pinSet.has(p.county_pin)||ids.has(p.parcel_objectid))throw Error('Ambiguous residential parcel identity');
  ids.add(p.parcel_objectid);pinSet.add(p.county_pin);
 }
 const scoreMap=mapUnique(roofing.records||[],'roofing score');
 const valueMap=mapUnique(valuation.records||[],'valuation');
 const imageMap=new Map();
 for(const x of (imagery.records||[])){
  const key=String(x.parcel_objectid||'');
  if(ids.has(key)&&(!imageMap.has(key)||String(x.last_checked_utc||'')>String(imageMap.get(key).last_checked_utc||'')))imageMap.set(key,x);
 }
 const permitMap=new Map(),permitKeys=new Set();
 for(const x of permits.records||[]){
  const id=String(x.parcel_objectid||''),key=id+'|'+String(x.permit_number||'');
  if(!ids.has(id)||!x.permit_number||permitKeys.has(key))throw Error('Unmatched or duplicate municipal permit');
  permitKeys.add(key);
  const arr=permitMap.get(id)||[];arr.push(x);permitMap.set(id,arr);
 }
 const records=originals.map(p=>{
  const id=p.parcel_objectid, r=scoreMap.get(id),v=valueMap.get(id)?.valuation,img=imageMap.get(id),matches=permitMap.get(id)||[];
  if(!r||r.county_pin!==p.county_pin)throw Error('Missing/mismatched roof-score evidence for parcel '+id);
  if(r.roof?.roof_condition_score!=null&&r.roof?.status!=='REVIEWED_ROOF_EVIDENCE_SCORE')throw Error('Unreviewed physical score blocked');
  if(!r.review?.not_a_damage_score||!Number.isInteger(r.review.data_review_priority)||r.review.data_review_priority<0||r.review.data_review_priority>100)throw Error('Review priority not evidence-gated');
  const verifiedImage=img?.imagery==='GOVERNMENT_REMOTE_JPEG_VERIFIED'&&sha(img.imagery_sha256)&&String(img.imagery_source_url||'').startsWith('https://imageserver.gisdata.mn.gov/');
  const listing=matches.map(m=>({
   permit_number:m.permit_number,issued_date:m.issued_date||null,
   classification:m.permit_kind,review_status:m.review_status,
   export_report:m.source_report,roof_scope_reference:m.third_party_corroboration?.url||null,
   final_roof_replacement_verified:false
  }));
  return {
   parcel_objectid:id,county_pin:p.county_pin,address:p.address,subdivision:p.plat_name,
   residential_candidate:true,year_built:n(v?.year_built)??n(p.year_built),
   valuation_usd:v?.gatekeeper==='SOURCE_RECORDED'?n(v.amount_usd):null,
   valuation_assessment_year:v?.assessment_year||null,
   valuation_review_status:v?.review_status||'PENDING',
   permit_matches:listing,permit_history_complete:false,
   roof_permit_candidate:listing.some(x=>x.classification==='ROOF_CANDIDATE_PENDING_DOCUMENT_REVIEW'),
   image_response_verified_in_source_ledger:Boolean(verifiedImage),
   image_source_url:verifiedImage?img.imagery_source_url:null,
   image_sha256:verifiedImage?img.imagery_sha256:null,
   imagery_is_condition_evidence:false,
   research_priority:r.review.data_review_priority,
   research_priority_is_damage_score:false,
   research_priority_reasons:r.review.priority_factors||[],
   roof_condition_score:r.roof?.status==='REVIEWED_ROOF_EVIDENCE_SCORE'?r.roof.roof_condition_score:null,
   roof_condition_review_status:r.roof?.status||'NOT_SCORED',
   mindex_score:null,
   gatekeeper_release_approved:false,
   outstanding_gates:[
     'ORIGINAL_MUNICIPAL_PERMIT_REVIEW','HUMAN_CONDITION_EVIDENCE_REVIEW','EVIDENCE_SUPPORTED_MINDEX'
   ],
   official_parcel_source:p.source_record_url,
   official_permit_search:'https://eagan.onlama.com/Search.aspx'
  };
 });
 return {
  status:'EVIDENCE_REGISTER_NOT_PHYSICAL_INSPECTION',
  checked_source_join_utc:new Date().toISOString(),
  original_60_only:true,
  counts:{
   residential_properties:records.length,
   municipal_export_permit_matches:permitKeys.size,
   residential_properties_with_permit_matches:permitMap.size,
   valuations_source_matched:records.filter(x=>x.valuation_usd!==null).length,
   government_imagery_response_hashes:records.filter(x=>x.image_response_verified_in_source_ledger).length,
   research_priority_cards:records.filter(x=>Number.isInteger(x.research_priority)).length,
   human_reviewed_roof_scores:records.filter(x=>x.roof_condition_score!==null).length,
   evidence_approved_mindex:0
  },
  source_reports:Object.values(FILES),
  limitations:['Permit CSV rows still need issuer-document review','An image response hash does not verify roof damage','Roof condition and Mindex are unscored pending human evidence'],
  records
 };
}
async function load(){
 if(memory.value&&Date.now()<memory.until)return memory.value;
 const entries=await Promise.all(Object.entries(FILES).map(async ([key,file])=>{
  const r=await fetch(BASE+file,{headers:{Accept:'application/json,text/csv'},signal:AbortSignal.timeout(12000)});
  if(!r.ok)throw Error('Evidence source '+file+' HTTP '+r.status);
  return [key,file.endsWith('.csv')?await r.text():await r.json()];
 }));
 const value=assemble(Object.fromEntries(entries));
 memory={value,until:Date.now()+120000};
 return value;
}
export default async function handler(req,res){
 res.setHeader('Cache-Control','private, no-store');
 res.setHeader('X-Content-Type-Options','nosniff');
 if(req.method!=='GET')return res.status(405).json({error:'GET required'});
 if(!process.env.AERO_ACCESS_PASSCODE||!process.env.AERO_SESSION_SECRET||!authorized(req))return res.status(401).json({error:'GateKeeper session required'});
 try{
  const result=await load();
  const limit=req.query?.limit==='20'?20:60;
  const q=String(req.query?.q||'').toLowerCase().trim().slice(0,120);
  const selected=[...result.records].sort((a,b)=>b.research_priority-a.research_priority||a.county_pin.localeCompare(b.county_pin))
   .filter(x=>!q||(x.county_pin+' '+x.address).toLowerCase().includes(q)).slice(0,limit);
  return res.status(200).json({...result,returned:selected.length,requested_limit:limit,records:selected});
 }catch(e){return res.status(503).json({error:'Evidence feed not ready; no scorecards fabricated',detail:String(e.message||e).slice(0,160)})}
}
