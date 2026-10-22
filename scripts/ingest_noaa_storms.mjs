/**
 * NOAA / NCEI Storm Events — real public-data ingest for AeroLeadAI.
 * Reads authoritative CSV.gz archives. Never infers an individual roof hit.
 * Only server-side GitHub Actions executes this; no API keys or Base44.
 */
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {join} from 'node:path';
const DIR='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/';
const D='evidence/data';
const TYPES=new Set(['HAIL','THUNDERSTORM WIND','TORNADO','HIGH WIND','STRONG WIND']);
const f=x=>x!==''&&x!==null&&x!==undefined&&Number.isFinite(Number(x))?Number(x):null;
export const distanceKm=(a,b,c,d)=>{const r=Math.PI/180,q=Math.sin((c-a)*r/2)**2+Math.cos(a*r)*Math.cos(c*r)*Math.sin((d-b)*r/2)**2;return 12742.0176*Math.asin(Math.min(1,Math.sqrt(q)));};
export function csvRows(s){
 const rows=[];let row=[],cell='',quote=false;
 for(let i=0;i<s.length;i++){
  const c=s[i];
  if(c==='"'){if(quote&&s[i+1]==='"'){cell+='"';i++}else quote=!quote}
  else if(c===','&&!quote){row.push(cell);cell=''}
  else if((c==='\n'||c==='\r')&&!quote){if(c==='\r'&&s[i+1]==='\n')i++;row.push(cell);if(row.some(x=>x!==''))rows.push(row);row=[];cell=''}
  else cell+=c
 }
 if(quote)throw Error('NOAA CSV quoted field not closed');
 if(row.length||cell){row.push(cell);rows.push(row)}
 return rows;
}
export function extract(csv,filename,geo,radiusKm=30){
 const rows=csvRows(csv),header=rows.shift();
 if(!header)throw Error('Empty official NOAA CSV');
 for(const name of ['EVENT_ID','STATE','EVENT_TYPE','BEGIN_DATE_TIME','CZ_NAME','BEGIN_LAT','BEGIN_LON','MAGNITUDE'])
   if(!header.includes(name))throw Error('NOAA schema missing '+name);
 const fields=Object.fromEntries(header.map((h,i)=>[h,i]));
 const events=[],seen=new Set();
 for(const row of rows){
  const get=k=>row[fields[k]]??'';
  if(get('STATE').toUpperCase()!=='MINNESOTA')continue;
  const type=get('EVENT_TYPE').trim().toUpperCase();
  if(!TYPES.has(type))continue;
  const id=get('EVENT_ID').trim(),lat=f(get('BEGIN_LAT')),lon=f(get('BEGIN_LON'));
  if(!id||seen.has(id))continue;
  const valid=lat!==null&&lon!==null&&lat>=40&&lat<=50&&lon>=-98&&lon<=-89;
  const nearest=valid?Math.min(...geo.map(x=>distanceKm(x.lat,x.lon,lat,lon))):null;
  const countyReport=get('CZ_NAME').trim().toUpperCase()==='DAKOTA'&&get('CZ_TYPE').trim().toUpperCase()==='C';
  if(!(nearest!==null&&nearest<=radiusKm)&&!countyReport)continue;
  seen.add(id);
  const mag=f(get('MAGNITUDE'));
  const date=get('BEGIN_DATE_TIME');
  // NOAA bulk CSV uses strings such as 31-JUL-24 17:30:00 in the source timezone.
  // Sort by calendar components, without asserting that the timestamp is UTC.
  const match=/^(\d{1,2})-([A-Z]{3})-(\d{2,4})\s+(\d{2}:\d{2}:\d{2})$/i.exec(date);
  const months=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const monthIndex=match?months.indexOf(match[2].toUpperCase())+1:0;
  const y=match?Number(match[3]):0;
  const year=y<100?(y<80?2000+y:1900+y):y;
  const sortKey=match&&monthIndex?String(year).padStart(4,'0')+'-'+String(monthIndex).padStart(2,'0')+
    '-'+match[1].padStart(2,'0')+'T'+match[4]:null;
  events.push({
    id,kind:type,begin_at:get('BEGIN_DATE_TIME'),end_at:get('END_DATE_TIME')||null,county:get('CZ_NAME'),
    point_lat:valid?lat:null,point_lon:valid?lon:null,
    distance_to_nearest_indexed_parcel_km:nearest===null?null:Number(nearest.toFixed(2)),
    hail_inches:type==='HAIL'?mag:null,
    wind_mph:type.includes('WIND')&&mag!==null?Number((mag*1.150779).toFixed(1)):null,
    wind_original_knots:type.includes('WIND')?mag:null,wind_magnitude_type:get('MAGNITUDE_TYPE')||null,
    source_file:filename,report_source:get('SOURCE')||null,sort_key:sortKey,
    geographic_confidence:nearest!==null&&nearest<=radiusKm?'REPORTED_POINT_ONLY_NOT_A_STORM_FOOTPRINT':'COUNTY_CONTEXT_ONLY_NOT_ADDRESS_SPECIFIC',
    damage_to_any_individual_property_confirmed:false
  });
 }
 return events;
}
async function bounded(url,maxBytes){
 const response=await fetch(url,{signal:AbortSignal.timeout(65000),headers:{'User-Agent':'AeroLeadAI-GateKeeper-Research/2.0','Accept':'*/*'}});
 if(!response.ok)throw Error('NOAA source HTTP '+response.status+' '+url);
 if(Number(response.headers.get('content-length')||0)>maxBytes)throw Error('NOAA response exceeds bound');
 const result=Buffer.from(await response.arrayBuffer());
 if(result.length>maxBytes)throw Error('NOAA response exceeded byte budget');return result;
}
export async function collect({directory=D,years=[2024,2025,2026],download=bounded}={}){
 const seed=JSON.parse(await readFile(join(directory,'imagery_manifest.json'),'utf8'));
 const outward=JSON.parse(await readFile(join(directory,'outward_ring_candidates.json'),'utf8'));
 if(seed.records?.length!==60||outward.source_query_completed!==true||outward.errors?.length)
   throw Error('Source inventory incomplete; do not infer storm geography');
 const geo=[...seed.records.map(x=>({lat:x.center_lat,lon:x.center_lon})),
   ...outward.ring_candidates.map(x=>({lat:x.center_lat,lon:x.center_lon}))];
 if(geo.some(x=>!Number.isFinite(x.lat)||!Number.isFinite(x.lon)))throw Error('GIS coordinates incomplete');
 const catalog=(await download(DIR,4_000_000)).toString('utf8');
 const byId=new Map(),files=[],errors=[];
 for(const year of years){
  const filename=[...catalog.matchAll(/StormEvents_details-ftp_v1\.0_d\d{4}_c\d{8}\.csv\.gz/g)]
    .map(x=>x[0]).filter(x=>x.includes('_d'+year+'_')).sort().at(-1);
  if(!filename){errors.push({year,error:'Source has no archive for requested year'});continue}
  try{
   const packed=await download(DIR+filename,24_000_000);
   const csv=gunzipSync(packed,{maxOutputLength:215_000_000}).toString('utf8');
   const matched=extract(csv,filename,geo);
   for(const e of matched)byId.set(e.id,e);
   files.push({year,file:filename,source_url:DIR+filename,scoped_event_count:matched.length,downloaded_bytes:packed.length});
  }catch(e){errors.push({year,error:String(e.message||e).slice(0,200)})}
 }
 if(!files.length)throw Error('NOAA storm feed failed; no guessed events written: '+JSON.stringify(errors));
 const events=[...byId.values()].sort((a,b)=>String(b.sort_key||'').localeCompare(String(a.sort_key||'')));

 const doc={format:'GATEKEEPER_NOAA_STORM_EVENTS_V1',
  retrieved_at_utc:new Date().toISOString(),provider:'NOAA NCEI Storm Events Database',
  official_directory:DIR,years_requested:years,years_retrieved:files.map(x=>x.year),
  files,errors,partial:errors.length>0,report_count:events.length,events,
  interpretation:'Nearby weather reports and county observations only. No verified storm footprint or roof damage. Wind magnitudes in knots converted to mph.',
  no_property_damage_verdicts:true,unobserved_means_unknown:true};
 await mkdir(directory,{recursive:true});
 await writeFile(join(directory,'noaa_storm_events_scoped.json'),JSON.stringify(doc,null,2)+'\n');
 console.log(JSON.stringify({years:doc.years_retrieved,events:events.length,partial:doc.partial,errors}));
 return doc;
}
if(process.argv[1]&&import.meta.url===new URL('file://'+process.argv[1]).href)
 collect().catch(e=>{console.error(e);process.exitCode=1});
