/**
 * Operational truth: one status per independent source; no false "all green".
 * A dashboard reachability check does not imply city permit-history completion.
 */
const ROOT='https://raw.githubusercontent.com/zaccboi8484/aero1/main/evidence/data/';
const SOURCES=[
 {id:'discovery',name:'Official ArcGIS parcel discovery',file:'outward_ring_candidates.json',timestamp:'generated_at_utc',hours:40,
  url:'https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2',message:'Official parcel identities, GIS coordinate records, and expanding rings'},
 {id:'parcels',name:'Individual GIS / regional permit crawler',file:'fast_validation_report.json',timestamp:'run_utc',hours:1,
  url:'https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2',message:'Rotating source checks; regional permits are not municipal reroof history'},
 {id:'bulk',name:'Bulk county PIN / GIS verification',file:'parcel_identity_bulk.json',timestamp:'checked_at_utc',hours:3,
  url:'https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2',message:'Fast official GIS identity check; not property-condition verification'},
 {id:'zip',name:'Census ZIP-area reported NOAA point overlay',file:'zcta_storm_index.json',timestamp:'generated_at_utc',hours:48,
  url:'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer/2',
  message:'Census ZCTA approximates USPS ZIP; a NOAA point reported inside ZIP-area is not a property strike'},
 {id:'storm',name:'NOAA Storm Events archives',file:'noaa_storm_events_scoped.json',timestamp:'retrieved_at_utc',hours:40,
  url:'https://www.ncei.noaa.gov/access/storm-events-database/',message:'Reported storm events; no inferred property-specific hail footprint'},
 {id:'permits',name:'City of Eagan permit issuer',file:'municipal_permit_export_audit.json',timestamp:'generated_at_utc',hours:null,
  url:'https://eagan.onlama.com/Dashboard.aspx',message:'Imported historical report matches only; full issuer history and final inspections unavailable'}
];
const time=s=>{const d=Date.parse(s||'');return Number.isFinite(d)?d:null};
export function classifySource(s,payload,now=Date.now()){
 if(!payload)return {state:'UNAVAILABLE',lastChecked:null,message:'Published source file unavailable'};
 if(s.id==='permits')return {state:'BLOCKED',lastChecked:payload.generated_at_utc||null,
  message:'Owner-supplied report matches: '+(payload.matched_permit_events??'unknown')+
    '. Direct City portal denied unattended access; original documents and final inspections not independently retrieved.'};
 const at=time(payload[s.timestamp]),age=at===null?null:Math.max(0,(now-at)/3600000);
 let status=age!==null&&age<=s.hours?'CURRENT':'STALE';
 if(s.id==='discovery'&&(payload.source_query_completed!==true||payload.errors?.length))status='DEGRADED';
 if(s.id==='bulk'&&(payload.complete!==true||!Number.isInteger(payload.matched)))status='DEGRADED';
 if(s.id==='storm'&&(payload.partial||payload.errors?.length))status='DEGRADED';
 if(s.id==='zip'&&(payload.format!=='GATEKEEPER_CENSUS_ZCTA_NOAA_POINTS_V1'||payload.parcels_unmapped>0||payload.source_partial))status='DEGRADED';
 return {state:status,lastChecked:payload[s.timestamp]||null,message:s.message};
}
let cache={value:null,until:0};
export default async function handler(req,res){
 res.setHeader('Cache-Control','public, max-age=0, s-maxage=90');
 res.setHeader('X-Content-Type-Options','nosniff');
 if(req.method!=='GET')return res.status(405).json({error:'GET required'});
 if(cache.value&&cache.until>Date.now())return res.status(200).json(cache.value);
 const fetched=await Promise.all(SOURCES.map(async s=>{
  try{
   const r=await fetch(ROOT+s.file,{cache:'no-store',signal:AbortSignal.timeout(11500)});
   if(!r.ok)throw Error('HTTP '+r.status);
   return {...s,...classifySource(s,await r.json())};
  }catch(e){return {...s,state:'UNAVAILABLE',lastChecked:null,message:String(e.message||e).slice(0,125)}}
 }));
 const state=fetched.some(x=>x.state==='BLOCKED'||x.state==='STALE'||x.state==='UNAVAILABLE'||x.state==='DEGRADED')?'DEGRADED':'HEALTHY';
 const payload={
  format:'GATEKEEPER_OPERATIONAL_TRUTH_V1',generatedAt:new Date().toISOString(),
  state,conditionsCertified:0,issuerPermitDocumentsReviewed:0,
  sourceHealthOnly:true,noBackendDataMigrationClaim:true,
  blockedSources:fetched.filter(x=>x.state==='BLOCKED'||x.state==='UNAVAILABLE').map(x=>x.id),
  staleSources:fetched.filter(x=>x.state==='STALE').map(x=>x.id),
  sources:fetched.map(x=>({id:x.id,name:x.name,state:x.state,lastChecked:x.lastChecked,url:x.url,message:x.message})),
  note:'A READY Vercel deployment, a collected city-report match, or verified GIS coordinates are not a physical roof condition or complete permit search.'
 };
 cache={value:payload,until:Date.now()+90000};
 return res.status(200).json(payload);
}
