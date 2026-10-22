/**
 * AeroLeadAI / GateKeeper — source-verified ZIP-area storm index.
 *
 * The U.S. Census Bureau's 2020 ZCTA polygon is a statistical approximation to
 * a USPS ZIP, not a postal-route guarantee. A NOAA Storm Events coordinate
 * inside that area verifies ONLY that an NWS storm observation was REPORTED
 * at a point inside the ZCTA on its recorded date. It does not establish a
 * storm footprint, roof strike, hail size at every address, or property damage.
 *
 * This script uses authentic Census TIGERweb ArcGIS polygon geometry, joins
 * actual source GIS parcel centroids and previously fetched NOAA reports, and
 * only writes data after successfully validating authoritative source inputs.
 * It does not call Base44, scrape restricted municipal portals, or invent hits.
 */
import {createHash} from 'node:crypto';
import {readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';

export const CENSUS_ZCTA_LAYER='https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer/2/query';
export const STORM_INDEX_VERSION='GATEKEEPER_CENSUS_ZCTA_NOAA_POINTS_V1';
const ROOT='evidence/data';
const isPoint=(lat,lon)=>typeof lat==='number'&&Number.isFinite(lat)&&lat>=-90&&lat<=90&&
 typeof lon==='number'&&Number.isFinite(lon)&&lon>=-180&&lon<=180;
const norm=v=>String(v??'').trim();

function onSegment(x,y,ax,ay,bx,by){
 const cross=(y-ay)*(bx-ax)-(x-ax)*(by-ay);
 if(Math.abs(cross)>1e-10)return false;
 return x>=Math.min(ax,bx)-1e-10&&x<=Math.max(ax,bx)+1e-10&&
        y>=Math.min(ay,by)-1e-10&&y<=Math.max(ay,by)+1e-10;
}
export function ringContains(lon,lat,ring){
 if(!Array.isArray(ring)||ring.length<4)return false;
 let inside=false;
 for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const a=ring[i],b=ring[j];
  if(!Array.isArray(a)||!Array.isArray(b)||!Number.isFinite(a[0])||!Number.isFinite(a[1])||
     !Number.isFinite(b[0])||!Number.isFinite(b[1]))throw Error('Invalid Census ring vertex');
  if(onSegment(lon,lat,a[0],a[1],b[0],b[1]))return true;
  if(((a[1]>lat)!==(b[1]>lat))&&lon<(b[0]-a[0])*(lat-a[1])/(b[1]-a[1])+a[0])
   inside=!inside;
 }
 return inside;
}
export function zctaAt(lon,lat,shapes){
 if(!isPoint(lat,lon))return null;
 const found=shapes.filter(shape=>{
  let parity=false;
  for(const ring of shape.rings){
   if(ringContains(lon,lat,ring))parity=!parity; // toggling honors holes
  }
  return parity;
 });
 if(found.length>1)throw Error('Conflicting overlapping official Census ZCTA polygons');
 return found.length?found[0].zcta:null;
}
export function normalizeNoaaDate(value){
 const s=norm(value);
 const day=/^(\d{1,2})-([A-Z]{3})-(\d{2,4})(?:\s+(\d{2}):(\d{2}):(\d{2}))?$/i.exec(s);
 const months=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
 if(day){
  const m=months.indexOf(day[2].toUpperCase())+1;let y=Number(day[3]);
  if(y<100)y+=y<80?2000:1900;
  const d=Number(day[1]);
  if(m>=1&&d>=1&&d<=new Date(Date.UTC(y,m,0)).getUTCDate() &&
     (!day[4]||(Number(day[4])<24&&Number(day[5])<60&&Number(day[6])<60))){
   return {date:[y,String(m).padStart(2,'0'),String(d).padStart(2,'0')].join('-'),
    localTime:day[4]?day.slice(4,7).join(':'):null,original:s};
  }
 }
 const iso=/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/.exec(s);
 if(iso&&Number(iso[2])>=1&&Number(iso[2])<=12&&Number(iso[3])>=1&&
    Number(iso[3])<=new Date(Date.UTC(Number(iso[1]),Number(iso[2]),0)).getUTCDate())
  return {date:iso[1]+'-'+iso[2]+'-'+iso[3],localTime:iso[4]?iso[4]+':'+iso[5]+':'+(iso[6]||'00'):null,original:s};
 return {date:null,localTime:null,original:s};
}
export function validateCensusGeo(payload){
 if(payload?.error)throw Error('Census ArcGIS returned an explicit error');
 if(payload?.exceededTransferLimit)throw Error('Census ZCTA result truncated');
 if(!Array.isArray(payload?.features)||!payload.features.length)throw Error('Official ZCTA polygon response empty');
 const shapes=[],seen=new Set();
 for(const item of payload.features){
  const zcta=norm(item?.attributes?.ZCTA5);
  if(!/^\d{5}$/.test(zcta)||seen.has(zcta)||!Array.isArray(item?.geometry?.rings)||
    item.geometry.rings.length===0)throw Error('Invalid or duplicate Census ZCTA polygon');
  if(!item.geometry.rings.every(r=>Array.isArray(r)&&r.length>=4))throw Error('Invalid ring');
  seen.add(zcta);shapes.push({zcta,rings:item.geometry.rings,
    geometrySha256:createHash('sha256').update(JSON.stringify(item.geometry.rings)).digest('hex')});
 }
 return shapes;
}
export function makeZipStormIndex({seed,rings,noaa,census,sourceUrl=CENSUS_ZCTA_LAYER}){
 if(seed?.records?.length!==60||rings?.source_query_completed!==true||
    !Array.isArray(rings?.ring_candidates)||rings.candidate_count!==rings.ring_candidates.length||
    rings.errors?.length)throw Error('Actual official GIS inventory unavailable or incomplete');
 if(noaa?.format!=='GATEKEEPER_NOAA_STORM_EVENTS_V1'||!Array.isArray(noaa.events)||
    noaa.report_count!==noaa.events.length||!noaa.retrieved_at_utc)
  throw Error('Authoritative NOAA Storm Events snapshot absent');
 const geo=[...seed.records,...rings.ring_candidates];
 const seen=new Set(),parcels=[];
 const shapes=validateCensusGeo(census);
 for(const p of geo){
  const oid=norm(p.parcel_objectid),pin=norm(p.county_pin);
  if(!oid||!pin||seen.has(pin)||!isPoint(p.center_lat,p.center_lon))
   throw Error('Source inventory has duplicate PIN or invalid coordinates');
  seen.add(pin);
  const zcta=zctaAt(p.center_lon,p.center_lat,shapes);
  parcels.push({parcel_objectid:oid,county_pin:pin,zcta,
    geographic_method:zcta?'2020_CENSUS_ZCTA_CENTROID_OVERLAY':'ZIP_AREA_UNRESOLVED',
    no_usps_delivery_verification:true});
 }
 const eventSeen=new Set(),eventsByZip=new Map(),unlocated=[];
 for(const e of noaa.events){
  const id=norm(e?.id);
  if(!id||eventSeen.has(id))throw Error('NOAA source storm IDs missing or duplicated');
  eventSeen.add(id);
  const located=isPoint(e.point_lat,e.point_lon);
  const zcta=located?zctaAt(e.point_lon,e.point_lat,shapes):null;
  const dt=normalizeNoaaDate(e.begin_at);
  if(!located||!zcta||!dt.date){unlocated.push(id);continue}
  const record={event_id:id,date:dt.date,local_time:dt.localTime,source_date_text:dt.original,
   event_type:norm(e.kind),zcta,hail_inches:typeof e.hail_inches==='number'?e.hail_inches:null,
   wind_mph:typeof e.wind_mph==='number'?e.wind_mph:null,point_lat:e.point_lat,point_lon:e.point_lon,
   source_archive:e.source_file||null,county:e.county||null,
   report_classification:'NWS_REPORTED_POINT_WITHIN_CENSUS_ZCTA',
   not_a_storm_footprint:true,not_confirmed_at_any_particular_roof:true};
  if(!eventsByZip.has(zcta))eventsByZip.set(zcta,[]);
  eventsByZip.get(zcta).push(record);
 }
 for(const rows of eventsByZip.values())rows.sort((a,b)=>b.date.localeCompare(a.date)||b.source_date_text.localeCompare(a.source_date_text));
 const matched=parcels.filter(p=>p.zcta!==null).length;
 if(!matched)throw Error('No parcel was located in an official ZIP-area polygon');
 const zctas=shapes.map(s=>({zcta:s.zcta,geometry_sha256:s.geometrySha256,
  report_points:eventsByZip.get(s.zcta)?.length||0}));
 const entries=[...eventsByZip].map(([zcta,records])=>({zcta,report_count:records.length,
  reports:records})).sort((a,b)=>a.zcta.localeCompare(b.zcta));
 return {format:STORM_INDEX_VERSION,generated_at_utc:new Date().toISOString(),
  source_zcta_layer:sourceUrl,zcta_boundary_vintage:'2020 Census',
  geographic_interpretation:'Census ZIP Code Tabulation Area (ZCTA) approximate USPS delivery ZIP, not proof of a postal ZIP for every address',
  noaa_run_at_utc:noaa.retrieved_at_utc,noaa_source_archive_count:noaa.report_count,
  source_partial:Boolean(noaa.partial),census_polygon_count:shapes.length,
  parcel_count:parcels.length,parcels_mapped:matched,parcels_unmapped:parcels.length-matched,
  event_points_in_scope:entries.reduce((n,x)=>n+x.report_count,0),events_without_zip_point:unlocated.length,
  zip_areas:zctas,parcels,events_by_zip:entries,
  evidence_meaning:'An actual NOAA event point was recorded inside a Census ZCTA on its reported date. It does not establish that the entire ZIP or any specific roof was struck.',
  not_a_property_storm_damage_certification:true,no_storm_footprint_claim:true};
}
export async function run({directory=ROOT,fetcher=fetch}={}){
 const [seed,rings,noaa]=await Promise.all(
  ['imagery_manifest.json','outward_ring_candidates.json','noaa_storm_events_scoped.json']
   .map(async name=>JSON.parse(await readFile(join(directory,name),'utf8'))));
 const parcels=[...seed.records,...rings.ring_candidates];
 if(parcels.some(p=>!isPoint(p.center_lat,p.center_lon)))throw Error('Invalid source parcel geo-coordinates');
 const box={xmin:Math.min(...parcels.map(p=>p.center_lon))-.014,
  xmax:Math.max(...parcels.map(p=>p.center_lon))+.014,
  ymin:Math.min(...parcels.map(p=>p.center_lat))-.014,
  ymax:Math.max(...parcels.map(p=>p.center_lat))+.014,spatialReference:{wkid:4326}};
 const query=new URLSearchParams({f:'json',geometry:JSON.stringify(box),geometryType:'esriGeometryEnvelope',
  inSR:'4326',outSR:'4326',spatialRel:'esriSpatialRelIntersects',
  outFields:'ZCTA5',returnGeometry:'true',resultRecordCount:'250'});
 const resp=await fetcher(CENSUS_ZCTA_LAYER+'?'+query,{headers:{'Accept':'application/json',
   'User-Agent':'AeroLeadAI-GateKeeper-ZCTA-Overlay/1.0'},signal:AbortSignal.timeout(55000)});
 if(!resp.ok)throw Error('U.S. Census TIGERweb HTTP '+resp.status);
 const payload=await resp.json();
 const out=makeZipStormIndex({seed,rings,noaa,census:payload,sourceUrl:CENSUS_ZCTA_LAYER+'?'+query});
 await writeFile(join(directory,'zcta_storm_index.json'),JSON.stringify(out,null,2)+'\n');
 console.log(JSON.stringify({parcels:out.parcel_count,with_zcta:out.parcels_mapped,
  zcta_count:out.census_polygon_count,NOAA_points_with_ZCTA:out.event_points_in_scope,
  storm_feed_partial:out.source_partial}));
 return out;
}
if(process.argv[1]&&import.meta.url===new URL('file://'+process.argv[1]).href)
 run().catch(e=>{console.error('GATEKEEPER ZIP STORM: '+String(e.message||e));process.exitCode=1});
