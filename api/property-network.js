/* AeroLeadAI official-source property network: true GIS discovery, no 60-card cap.
 * Read-only public records; incomplete permit/storm searches remain explicitly UNKNOWN.
 */
import {permitCardFacts,stormCardFacts,roofReviewNeeds,calendarDate} from './property-card-intel.js';
const D='https://raw.githubusercontent.com/zaccboi8484/aero1/main/evidence/data/';
const FILES={seed:'imagery_manifest.json',rings:'outward_ring_candidates.json',checks:'fast_validation_report.json',
 permits:'municipal_permit_export_audit.json',roof:'roof_evidence_scores.json',
 valuations:'live_property_enrichment.json',storm:'noaa_storm_events_scoped.json',bulk:'parcel_identity_bulk.json',zip:'zcta_storm_index.json'};
let memo={until:0,result:null};
const key=v=>String(v??'').trim();
const saneNum=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
const sourceUrl=u=>{try{const p=new URL(u);return p.protocol==='https:'&&
 ['arcgis.metc.state.mn.us','imageserver.gisdata.mn.gov','gis.cityofeagan.com',
  'eagan.onlama.com','www.ncei.noaa.gov'].includes(p.hostname)}catch{return false}};
function distance(a,b,c,d){const r=Math.PI/180,q=Math.sin((c-a)*r/2)**2+Math.cos(a*r)*Math.cos(c*r)*Math.sin((d-b)*r/2)**2;return 12742.0176*Math.asin(Math.min(1,Math.sqrt(q)))}
const maps=(items,label)=>{if(!Array.isArray(items))throw Error(label+' is missing');
 const m=new Map();for(const item of items){const id=key(item?.parcel_objectid);
  if(!id||m.has(id))throw Error(label+' has ambiguous GIS parcel ID');m.set(id,item)}return m};
export function joinEvidence(d){
 const seed=maps(d.seed?.records,'Original 60'),rings=maps(d.rings?.ring_candidates,'Official GIS rings');
 if(seed.size!==60||d.rings.source_query_completed!==true||d.rings.errors?.length||rings.size!==d.rings.candidate_count)
  throw Error('Official parcel discovery incomplete or original identities changed');
 const all=new Map(seed),pins=new Set([...seed.values()].map(x=>key(x.county_pin)));
 if(pins.size!==60)throw Error('Duplicate seed PIN');
 for(const [id,p]of rings){
  if(all.has(id)||!p.county_pin||pins.has(key(p.county_pin))||p.verification_status!=='OFFICIAL_GIS_SOURCE_CANDIDATE'||
     saneNum(p.center_lat)===null||saneNum(p.center_lon)===null)
   throw Error('GIS ring contains contradictory identity');
  all.set(id,p);pins.add(key(p.county_pin));
 }
 if(!Array.isArray(d.checks?.records))throw Error('GIS checks missing');
 const bulk=new Map();
 if(d.bulk?.format==='GATEKEEPER_BULK_GIS_PIN_V1'&&d.bulk.complete===true&&
    Array.isArray(d.bulk.records)&&d.bulk.records.length===d.bulk.matched){
  const seen=new Set();
  for(const x of d.bulk.records){
   const pin=key(x.county_pin);
   if(seen.has(pin))throw Error('Duplicate published GIS bulk PIN');
   seen.add(pin);
   if(x.status==='OFFICIAL_GIS_PIN_AND_ID_MATCHED')bulk.set(pin,{id:key(x.parcel_objectid),checkedAt:x.checked_at_utc});
  }
 }
  const checks=new Map();
 for(const c of d.checks.records){const k=key(c.county_pin);
  if(k&&(!checks.has(k)||String(c.last_checked_utc||'')>String(checks.get(k).last_checked_utc||'')))checks.set(k,c)}
 const roof=maps(d.roof?.records,'Research priorities'),values=maps(d.valuations?.records,'GIS valuations');
 const permits=new Map(),permitIds=new Set();
 if(!Array.isArray(d.permits?.records))throw Error('Issuer report record set missing');
 for(const r of d.permits.records){const id=key(r.parcel_objectid),no=key(r.permit_number);
  if(!seed.has(id)||!no||permitIds.has(no))throw Error('Duplicate or unassociated issuer CSV permit');
  permitIds.add(no);if(!permits.has(id))permits.set(id,[]);
  permits.get(id).push({number:no,issuedAt:r.issued_date||null,kind:r.permit_kind,stage:'OWNER_PROVIDED_REPORT_NOT_ISSUER_DOCUMENT',finalInspectionApproved:null})}
 if(permitIds.size!==d.permits.matched_permit_events)throw Error('Municipal export count does not match actual records');
 const stormSourcePublished=d.storm?.format==='GATEKEEPER_NOAA_STORM_EVENTS_V1'&&Array.isArray(d.storm.events);
 const reports=stormSourcePublished?d.storm.events:[];

 // A ZIP-area match requires the complete official parcel census and the
 // precise NOAA source snapshot. A stale ZIP overlay does not claim any hits.
 const zipCurrent=d.zip?.format==='GATEKEEPER_CENSUS_ZCTA_NOAA_POINTS_V1'&&
  d.zip.not_a_property_storm_damage_certification===true&&d.zip.parcel_count===all.size&&
  d.zip.noaa_run_at_utc===d.storm?.retrieved_at_utc&&Array.isArray(d.zip.parcels)&&
  d.zip.parcels.length===all.size&&Array.isArray(d.zip.events_by_zip);
 const zips=new Map(),eventsByZip=new Map();
 if(zipCurrent){
  const ids=new Set(reports.map(e=>key(e.id)));
  for(const entry of d.zip.parcels){
   const pin=key(entry.county_pin);
   if(!pin||zips.has(pin))throw Error('Duplicated source Census ZIP parcel PIN');
   zips.set(pin,entry);
  }
  if(zips.size!==all.size)throw Error('Incomplete source Census ZIP parcel census');
  for(const group of d.zip.events_by_zip){
   if(eventsByZip.has(group.zcta)||!Array.isArray(group.reports)||group.report_count!==group.reports.length)
    throw Error('Conflicting NOAA report ZIP groups');
   if(group.reports.some(e=>!ids.has(key(e.event_id))||e.zcta!==group.zcta||
       e.report_classification!=='NWS_REPORTED_POINT_WITHIN_CENSUS_ZCTA'||
       e.not_confirmed_at_any_particular_roof!==true||
       !/^\d{4}-\d{2}-\d{2}$/.test(String(e.date||''))))
    throw Error('Invalid storm claim in Census ZIP index');
   eventsByZip.set(group.zcta,group.reports);
  }
 }
 const records=[...all].map(([id,p])=>{
  const pin=key(p.county_pin),seedBatch=seed.has(id),check=checks.get(pin),official=bulk.get(pin);
  if(official&&official.id!==id)throw Error('Published bulk GIS object ID and original parcel conflict: '+pin);
  const priority=roof.get(id)?.review?.data_review_priority;
  const rv=roof.get(id);
  const evidencePriority=seedBatch&&rv?.review?.not_a_damage_score===true&&
    Number.isInteger(priority)&&priority>=0&&priority<=100?priority:null;
  const val=values.get(id)?.valuation;
  if(seedBatch&&(!rv||key(rv.county_pin)!==pin))throw Error('Original 60 roof research identity mismatch');
  if(val&&key(values.get(id).county_pin)!==pin)throw Error('GIS valuation PIN mismatch');
  const photo=check?.imagery==='GOVERNMENT_REMOTE_JPEG_VERIFIED'&&
    /^[a-f0-9]{64}$/i.test(String(check.imagery_sha256||''))&&sourceUrl(check.imagery_source_url);
  const storms=reports.map(e=>{
    if(saneNum(e.point_lat)===null||saneNum(e.point_lon)===null)return null;
    const km=distance(p.center_lat,p.center_lon,e.point_lat,e.point_lon);
    return km<=15?{id:e.id,kind:e.kind,date:e.begin_at,sortKey:e.sort_key||null,
      distanceKm:Number(km.toFixed(2)),hailInches:e.hail_inches,windMph:e.wind_mph,
      relation:'NEARBY_REPORT_NOT_PROPERTY_IMPACT'}:null;
  }).filter(Boolean);
  const permitFacts=permitCardFacts(permits.get(id)||[]);
  const stormFacts=stormCardFacts(storms,stormSourcePublished);
  const roofNeeds=roofReviewNeeds({yearBuilt:Number(p.year_built),permitFacts,stormFacts,sourceImageryVerified:Boolean(photo)});

  const zipSource=zipCurrent?zips.get(pin):null;
  if(zipSource&&key(zipSource.parcel_objectid)!==id)
   throw Error('Contradictory Census ZIP-area parcel identity');
  const zcta=zipSource?.zcta||null;
  const zipEvents=zcta?(eventsByZip.get(zcta)||[]):[];
  const zipReports=zipEvents.slice(0,12).map(e=>({
    id:e.event_id,kind:e.event_type,date:e.date,localTime:e.local_time,
    hailInches:e.hail_inches,windMph:e.wind_mph,
    sourceUrl:e.source_archive&&/^[a-zA-Z0-9_.-]+\.csv\.gz$/.test(e.source_archive)?
       'https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'+e.source_archive:null,
    relationship:'NOAA_REPORTED_POINT_INSIDE_CENSUS_ZCTA_NOT_CONFIRMED_ROOF_IMPACT'
  }));

  storms.sort((a,b)=>String(calendarDate(b.sortKey||b.date)||'').localeCompare(String(calendarDate(a.sortKey||a.date)||''))||
    a.distanceKm-b.distanceKm);
  return {id,pin,address:p.address,city:'Eagan',plat:p.plat_name||null,
   lat:p.center_lat,lon:p.center_lon,ring:seedBatch?0:p.ring,
   discovery:seedBatch?'ORIGINAL_RESEARCH_BATCH':'OFFICIAL_GIS_DISCOVERY_RING',
   parcelStatus:official?'OFFICIAL_PIN_CONFIRMED':(check?.parcel_validation||'GIS_SOURCE_CANDIDATE_PENDING_CHECK'),
   bulkPinValidated:Boolean(official),
   parcelCheckedAt:check?.last_checked_utc||null,
   parcelSource:sourceUrl(p.source_record_url)?p.source_record_url:null,
   researchPriority:evidencePriority,roofConditionScore:null,mindexScore:null,gatekeeperCertified:false,
   yearBuilt:p.year_built==null?null:Number(p.year_built)||null,
   valuationUsd:val?.gatekeeper==='SOURCE_RECORDED'&&saneNum(val.amount_usd)!==null?val.amount_usd:null,
   valuationEvidence:{amountUsd:val?.gatekeeper==='SOURCE_RECORDED'&&saneNum(val.amount_usd)!==null?val.amount_usd:null,
    assessmentYear:Number.isInteger(val?.assessment_year)?val.assessment_year:null,
    sourceStatus:val?.gatekeeper==='SOURCE_RECORDED'?'SOURCE_RECORDED':'NOT_VERIFIED',
    sourceUrl:sourceUrl(val?.source_url)?val.source_url:null},
   ownership:{recordedOwnerName:null,ownerType:'UNKNOWN',sourceStatus:'NOT_VERIFIED',
    sourceUrl:null,checkedAt:null,possibleOccupantName:null,
    note:'Recorded ownership and current residency require independent authoritative verification'},
   permits:permits.get(id)||[],permitFacts,stormFacts,roofNeeds,
   censusZcta:zcta,postalZipVerified:false,
   zipAreaStormStatus:!d.zip?'ZIP_AREA_INDEX_PENDING':!zipCurrent?'ZIP_AREA_INDEX_STALE':
      !zcta?'ZIP_AREA_UNRESOLVED':zipEvents.length?
      'NOAA_REPORT_POINT_WITHIN_CENSUS_ZCTA':'NO_PUBLISHED_NOAA_POINT_IN_ZCTA',
   zipAreaStormReports:zipReports,latestZipStorm:zipReports[0]||null,
   completeMunicipalPermitHistory:false,
   municipalPermitStatus:d.checks.municipal_permit_source?.status||'NOT_QUERIED',
   regionalPermitStatus:check?.regional_permits||'NOT_QUERIED',
   regionalPermitCount:check?.regional_permit_count??null,
   regionalSource:sourceUrl(check?.regional_source_url)?check.regional_source_url:null,
   aerialSourceVerified:Boolean(photo),aerialSource:photo?check.imagery_source_url:null,
   aerialRedistributionRightsVerified:false,stormReports:storms.slice(0,16),
   stormFeedStatus:stormSourcePublished?'NOAA_SOURCE_PUBLISHED':'NOAA_NOT_YET_RETRIEVED',
   evidenceStatus:seedBatch?'INITIAL_BATCH_UNDER_HUMAN_REVIEW':'DISCOVERY_SOURCE_ONLY'};
 });
 records.sort((a,b)=>(b.researchPriority??-1)-(a.researchPriority??-1)||a.pin.localeCompare(b.pin));
 return {status:'LIVE_DISCOVERY_NOT_DAMAGE_CERTIFICATION',updatedAt:new Date().toISOString(),
  sourceRunAt:d.checks.run_utc,bulkRunAt:d.bulk?.checked_at_utc||null,stormRunAt:d.storm?.retrieved_at_utc||null,
  stormDataPartial:d.storm?.partial??null,
  counts:{parcels:records.length,initialBatch:60,expansion:rings.size,
   checkedPins:records.filter(x=>x.parcelStatus==='OFFICIAL_PIN_CONFIRMED').length,
   parcelsAttemptedAtLeastOnce:records.filter(x=>x.parcelCheckedAt!==null).length,
   parcelsNeverAttempted:records.filter(x=>x.parcelCheckedAt===null).length,
   publishedAttemptCountLastRun:d.checks.batch_attempted??null,
   sourceScanAt:d.checks.run_utc??null,
   bulkPinVerified:records.filter(x=>x.bulkPinValidated).length,
   sourceValidatedImagery:records.filter(x=>x.aerialSourceVerified).length,
   municipalReportPermits:permitIds.size,municipalReportProperties:permits.size,
   datedPermitReportProperties:records.filter(p=>p.permitFacts.latestDate!==null).length,
   datedStormProximityProperties:records.filter(p=>p.stormFacts.latestDate!==null).length,
   roofReviewTasks:records.filter(p=>p.roofNeeds.status==='ROOF_CONDITION_UNKNOWN_NEEDS_REVIEW').length,
   historicalStormReports:reports.length,nearbyStormProperties:records.filter(x=>x.stormReports.length).length,
   censusZipAreaMapped:records.filter(x=>x.censusZcta).length,
   zipAreaNoaaPropertyMatches:records.filter(x=>x.zipAreaStormReports.length).length,
   zipAreaSourceStatus:!d.zip?'NOT_PUBLISHED':zipCurrent?'CURRENT':'STALE',
   certifiedRoofConditions:0,certifiedMindex:0,
   cityPermitPortalStatus:d.checks.municipal_permit_source?.status||'NOT_QUERIED',
   partialGISScan:d.checks.total_indexed<records.length},records};
}
async function load(){
 if(memo.result&&Date.now()<memo.until)return memo.result;
 const values=await Promise.all(Object.entries(FILES).map(async ([k,file])=>{
  const r=await fetch(D+file,{signal:AbortSignal.timeout(17000),cache:'no-store'});
  if(!r.ok&&(k==='storm'||k==='bulk'||k==='zip')&&r.status===404)return[k,null];
  if(!r.ok)throw Error(file+' HTTP '+r.status);
  return[k,await r.json()];
 }));
 const joined=joinEvidence(Object.fromEntries(values));
 memo={result:joined,until:Date.now()+75000};return joined;
}
export default async function handler(req,res){
 res.setHeader('Cache-Control','public, max-age=0, s-maxage=60');
 res.setHeader('X-Content-Type-Options','nosniff');
 if(req.method!=='GET')return res.status(405).json({error:'GET required'});
 try{
  const source=await load(),q=String(req.query?.q||'').trim().toLowerCase().slice(0,90);
  const type=String(req.query?.view||'all');
  const limit=Math.min(1000,Math.max(1,Number.parseInt(req.query?.limit,10)||250));
  const offset=Math.max(0,Number.parseInt(req.query?.offset,10)||0);
  const filtered=source.records.filter(x=>(!q||(x.address+' '+x.pin).toLowerCase().includes(q))&&
   (type==='all'||type==='rings'&&x.ring>0||type==='original'&&x.ring===0||
    type==='storm'&&x.stormReports.length>0||type==='permits'&&x.permits.length>0));
  return res.status(200).json({...source,totalMatches:filtered.length,offset,
   records:filtered.slice(offset,offset+limit),hasMore:offset+limit<filtered.length});
 }catch(e){return res.status(503).json({error:'Source-backed property network not ready; no fabricated records',detail:String(e.message||e).slice(0,210)})}
}
