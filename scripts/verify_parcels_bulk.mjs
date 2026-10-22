/**
 * GateKeeper bulk GIS identity audit — one official ArcGIS IN-query per 60 PINs.
 * Performs actual network requests; never equates parcel identity with roof damage.
 * A partial or truncated response fails the run and does not replace prior proof.
 */
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {join} from 'node:path';

export const GIS='https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2/query';
const ROOT='evidence/data';
export function canonicalInventory(seed,rings){
 if(seed?.records?.length!==60||rings?.source_query_completed!==true||rings?.errors?.length||
 !Array.isArray(rings?.ring_candidates)||rings.ring_candidates.length!==rings.candidate_count)
  throw Error('Official GIS inventory is incomplete');
 const a=[...seed.records,...rings.ring_candidates];
 const ids=new Set(),pins=new Set();
 for(const item of a){
  const id=String(item.parcel_objectid||''),pin=String(item.county_pin||'');
  if(!/^\d+$/.test(id)||!/^\d{9,16}$/.test(pin)||ids.has(id)||pins.has(pin))
   throw Error('Duplicate/invalid official parcel id/PIN');
  ids.add(id);pins.add(pin);
 }
 return a;
}
export function parseResponse(payload,expected){
 if(payload?.error)throw Error('Official GIS ArcGIS query error');
 if(payload?.exceededTransferLimit)throw Error('ArcGIS result truncated; fail closed');
 if(!Array.isArray(payload?.features))throw Error('Official GIS response missing features');
 const valid=new Map();
 for(const row of payload.features){
  const a=row?.attributes||{},pin=String(a.COUNTY_PIN||''),oid=String(a.OBJECTID||'');
  if(!expected.has(pin))continue;
  if(valid.has(pin))throw Error('Duplicate county PIN response: '+pin);
  if(!/^\d+$/.test(oid))throw Error('Invalid official GIS object ID');
  valid.set(pin,oid);
 }
 if(valid.size!==expected.size)throw Error('Some requested official GIS parcel identities were not returned');
 return valid;
}
export async function verify({directory=ROOT,fetcher=fetch,chunkSize=60}={}){
 const seed=JSON.parse(await readFile(join(directory,'imagery_manifest.json'),'utf8'));
 const rings=JSON.parse(await readFile(join(directory,'outward_ring_candidates.json'),'utf8'));
 const inventory=canonicalInventory(seed,rings);
 const checkedAt=new Date().toISOString();
 const result=[];
 for(let index=0;index<inventory.length;index+=chunkSize){
  const group=inventory.slice(index,index+chunkSize);
  const pins=new Set(group.map(x=>String(x.county_pin)));
  const clause="COUNTY_PIN IN ("+[...pins].map(pin=>"'"+pin+"'").join(',')+")";
  const url=GIS+'?'+new URLSearchParams({f:'json',where:clause,
    outFields:'OBJECTID,COUNTY_PIN',returnGeometry:'false',
    resultRecordCount:String(Math.max(chunkSize+10,100))});
  let response;
  for(let attempt=0;attempt<3;attempt++){
   try{
    response=await fetcher(url,{signal:AbortSignal.timeout(20000),
      headers:{'User-Agent':'AeroLeadAI-GateKeeper-GIS/2.1','Accept':'application/json'}});
    if(response.status===429||response.status>=500){if(attempt<2){await new Promise(r=>setTimeout(r,1200*(attempt+1)));continue}}
    if(!response.ok)throw Error('Official GIS HTTP '+response.status);
    break;
   }catch(e){if(attempt===2)throw e;await new Promise(r=>setTimeout(r,1200*(attempt+1)))}
  }
  if(!response?.ok)throw Error('Official GIS failed');
  const features=await response.json();
  const exact=parseResponse(features,pins);
  for(const row of group){
   const pin=String(row.county_pin),observed=exact.get(pin),expected=String(row.parcel_objectid);
   if(observed!==expected)throw Error('Parcel object ID conflicts with official PIN: '+pin);
   result.push({parcel_objectid:expected,county_pin:pin,
    status:'OFFICIAL_GIS_PIN_AND_ID_MATCHED',source_url:url,
    checked_at_utc:checkedAt,not_a_roof_or_permit_finding:true});
  }
 }
 if(result.length!==inventory.length||new Set(result.map(x=>x.county_pin)).size!==inventory.length)
  throw Error('Incomplete batch GIS proof');
 const record={format:'GATEKEEPER_BULK_GIS_PIN_V1',checked_at_utc:checkedAt,
  source:GIS,requested:inventory.length,matched:result.length,
  groups_queried:Math.ceil(result.length/chunkSize),complete:true,
  damage_findings:0,permit_history_verified:0,records:result};
 await mkdir(directory,{recursive:true});
 await writeFile(join(directory,'parcel_identity_bulk.json'),JSON.stringify(record,null,2)+'\n');
 console.log(JSON.stringify({complete:true,matched:record.matched,groups:record.groups_queried}));
 return record;
}
if(process.argv[1]&&import.meta.url===new URL('file://'+process.argv[1]).href)
 verify().catch(e=>{console.error('GIS BULK VERIFIED FAILED: '+e.message);process.exitCode=1});
