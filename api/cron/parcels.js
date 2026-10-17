/* AeroLeadAI daily Vercel parcel validation, Hobby daily cron.
 Stateless check; persistent 15-minute ingest is GitHub Actions. */
const SOURCE="https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2/query";
const CSV="https://raw.githubusercontent.com/zaccboi8484/aero1/main/evidence/data/kingswood_parcel_candidates.csv";
export default async function handler(req,res){
 res.setHeader("Cache-Control","no-store");res.setHeader("X-Content-Type-Options","nosniff");
 if(req.method!=="GET")return res.status(405).json({error:"GET required"});
 if(!process.env.CRON_SECRET||req.headers.authorization!=="Bearer "+process.env.CRON_SECRET)return res.status(401).json({error:"Unauthenticated scheduler request"});
 const checked=new Date().toISOString();let error=null,observed=[];
 try{
  const csv=await fetch(CSV,{signal:AbortSignal.timeout(7000),cache:"no-store"});if(!csv.ok)throw Error("Parcel seed registry unavailable");
  const lines=(await csv.text()).split(/\r?\n/).slice(1).filter(Boolean);
  const known=lines.map(row=>row.split(",")[1]).filter(s=>/^\d{12}$/.test(s));
  if(known.length<60)throw Error("Expected 60 sourced county PINs");
  const day=Math.floor(Date.now()/86400000);
  const pins=[...new Set(Array.from({length:8},(_,i)=>known[(day*8+i)%known.length]))];
  const u=SOURCE+"?"+new URLSearchParams({f:"json",where:"COUNTY_PIN IN ("+pins.map(p=>"'"+p+"'").join(",")+")",outFields:"OBJECTID,COUNTY_PIN,CTU_NAME,ANUMBER,ST_NAME",returnGeometry:"false",resultRecordCount:"100"});
  const r=await fetch(u,{cache:"no-store",signal:AbortSignal.timeout(12000)});
  if(!r.ok)throw Error("Official GIS HTTP "+r.status);const d=await r.json();if(d.error)throw Error("Official GIS rejected query");
  const found=new Set((d.features||[]).map(x=>String(x.attributes?.COUNTY_PIN||"")));
  observed=pins.map(pin=>({pin,official_source_match:found.has(pin)}));
 }catch(e){error=String(e.message||e).slice(0,180)}
 return res.status(error?502:200).json({checked_at_utc:checked,source:SOURCE,records_checked:observed.length,official_matches:observed.filter(x=>x.official_source_match).length,
  status:error?"OFFICIAL_SOURCE_ERROR":"QUERY_COMPLETED",error,not_property_condition_verification:true,
  provenance:"Stateless Vercel live check; durable crawl results published by GitHub Actions"});
}
