/* AeroLeadAI daily Vercel municipal + regional permit source checks.
 No login evasion; source reachability is not a completed address search. */
const CITY="https://eagan.onlama.com/Dashboard.aspx";
const REGIONAL="https://arcgis.metc.state.mn.us/server/rest/services/EnterpriseLibrary/DTATResidentialPermits/FeatureServer/0/query";
export default async function handler(req,res){
 res.setHeader("Cache-Control","no-store");res.setHeader("X-Content-Type-Options","nosniff");
 if(req.method!=="GET")return res.status(405).json({error:"GET required"});
 if(!process.env.CRON_SECRET||req.headers.authorization!=="Bearer "+process.env.CRON_SECRET)return res.status(401).json({error:"Unauthenticated scheduler request"});
 const result={checked_at_utc:new Date().toISOString(),source_list:[CITY,REGIONAL],municipal:"NOT_CHECKED",regional:"NOT_CHECKED",
  municipal_permit_records_verified:0,municipal_search_complete:false,
  note:"A public dashboard check or regional permit record does not verify any property's reroof permit."};
 try{
  const r=await fetch(CITY,{cache:"no-store",signal:AbortSignal.timeout(10000)});
  if(!r.ok)throw Error("Eagan public dashboard HTTP "+r.status);
  const html=await r.text();
  result.municipal=/Open Data|Monthly Permits/.test(html)?"PUBLIC_REPORT_UI_REACHABLE":"REPORT_UI_UNRECOGNIZED";
 }catch(e){result.municipal="SOURCE_ACCESS_BLOCKED_OR_UNAVAILABLE";result.municipal_error=String(e.message||e).slice(0,180)}
 try{
  const uri=REGIONAL+"?"+new URLSearchParams({f:"json",where:"UPPER(CTU_NAME) = 'EAGAN'",returnCountOnly:"true"});
  const r=await fetch(uri,{cache:"no-store",signal:AbortSignal.timeout(12000)});
  if(!r.ok)throw Error("Regional layer HTTP "+r.status);
  const d=await r.json();if(d.error)throw Error("Regional layer rejected query");
  result.regional="QUERY_COMPLETED";result.regional_eagan_record_count=Number.isInteger(d.count)?d.count:null;
 }catch(e){result.regional="SOURCE_ERROR";result.regional_error=String(e.message||e).slice(0,180)}
 const bothFailed=result.municipal!=="PUBLIC_REPORT_UI_REACHABLE"&&result.regional!=="QUERY_COMPLETED";
 return res.status(bothFailed?502:200).json(result);
}
