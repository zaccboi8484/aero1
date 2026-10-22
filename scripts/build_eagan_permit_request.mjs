/**
 * Exact source-based municipal issuer lookup packet across every Eagan GIS parcel.
 * NO direct Eagan scraping. Generates CSV for authorized City NextRequest upload,
 * plus a machine-readable audit of source/date/coverage.
 */
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {join} from 'node:path';
const ROOT='evidence/data';
const q=v=>{let s=String(v??'');if(/^[\s]*[=+\-@]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"'};
export function makePacket(original,rings,permitReport){
 if(!Array.isArray(original?.records)||original.records.length!==60)
  throw Error('Original source register is not the 60 source-backed properties');
 if(rings?.source_query_completed!==true||rings.errors?.length||!Array.isArray(rings.ring_candidates))
  throw Error('Cannot publish a municipal request from incomplete GIS discovery');
 const list=new Map(),pins=new Set();
 for(const p of [...original.records,...rings.ring_candidates]){
  const oid=String(p.parcel_objectid??''),pin=String(p.county_pin??'').trim(),address=String(p.address??'').trim();
  if(!/^\d+$/.test(oid)||!/^\d+$/.test(pin)||!address.endsWith(', Eagan, MN'))throw Error('Parcel identity missing or outside Eagan');
  if(list.has(oid)||pins.has(pin))throw Error('Duplicate parcel ID/PIN requires manual reconciliation');
  pins.add(pin);
  list.set(oid,{parcel_objectid:oid,county_pin:pin,address,
    origin:original.records.some(x=>String(x.parcel_objectid)===oid)?'INITIAL_60':'OFFICIAL_GIS_EXPANSION',
    permit_numbers:[],city_history_complete:false,issuer_documents_reviewed:0,city_source:'City of Eagan / NextRequest'});
 }
 const permits=permitReport?.records||[];
 if(!Array.isArray(permits)||permits.length!==Number(permitReport.matched_permit_events))
  throw Error('Permit export inventory mismatch; do not synthesize source matches');
 const used=new Set();
 for(const p of permits){
  const row=list.get(String(p.parcel_objectid??'')),no=String(p.permit_number??'').trim();
  if(!row||!no||used.has(no))throw Error('Unmatched or duplicate city permit event');
  row.permit_numbers.push(no);used.add(no);
 }
 const records=[...list.values()].sort((a,b)=>(a.origin===b.origin?0:a.origin==='INITIAL_60'?-1:1)||a.county_pin.localeCompare(b.county_pin));
 const headers=['parcel_objectid','county_pin','address','origin','permit_numbers_from_existing_city_reports','issuer_original_document_reviewed','complete_history_obtained','requested_records'];
 const csv=[headers.join(',')].concat(records.map(p=>[
  p.parcel_objectid,p.county_pin,p.address,p.origin,p.permit_numbers.join(';'),0,'NO',
  'Existing public permit history / roofing scope / inspection outcomes and final signoff'
 ].map(q).join(','))).join('\n')+'\n';
 return {csv,report:{
  format:'AEROLEADAI_PUBLIC_MUNICIPAL_RECORD_REQUEST_V1',generated_at_utc:new Date().toISOString(),
  source:'Metropolitan Council Dakota parcels / City of Eagan municipal report exports',
  city_records_request_url:'https://cityofeaganmn.nextrequest.com/',
  municipality:'Eagan, Minnesota',
  parcel_count:records.length,initial_research_batch:60,expansion:records.length-60,
  municipal_report_matches:used.size,complete_city_permit_histories_verified:0,
  original_city_issuer_permit_documents_reviewed:0,
  not_submitted:true,records_request_required:true,records_are_public_only:true,
  warning:'This packet has not been submitted. It requests existing public records; City will determine availability, access, fees and reasonable turnaround.'
 }};
}
export async function generate({directory=ROOT}={}){
 const data=await Promise.all(['imagery_manifest.json','outward_ring_candidates.json','municipal_permit_export_audit.json'].map(x=>readFile(join(directory,x),'utf8').then(JSON.parse)));
 const {csv,report}=makePacket(...data);
 await mkdir(directory,{recursive:true});
 await Promise.all([
  writeFile(join(directory,'eagan_municipal_record_request_all_parcels.csv'),csv,'utf8'),
  writeFile(join(directory,'eagan_municipal_record_request_status.json'),JSON.stringify(report,null,2)+'\n','utf8')
 ]);
 console.log(JSON.stringify({parcels:report.parcel_count,existing_report_matches:report.municipal_report_matches,submitted:false}));
 return report;
}
if(process.argv[1]&&import.meta.url===new URL('file://'+process.argv[1]).href)
 generate().catch(e=>{console.error(e);process.exitCode=1});
