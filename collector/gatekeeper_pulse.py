#!/usr/bin/env python3
"""AeroLeadAI GateKeeper autonomous source freshness pulse and human upgrade queue.
Human review required for scoring, credentials, release and property-condition claims.
"""
import argparse,datetime as dt,hashlib,json,pathlib
SOURCES={"parcels":("collection_manifest.json","collected_at_utc",36,"count"),
         "gis_geometry":("subdivision_geometry_checks.json","generated_at_utc",72,None),
         "mn_addresses":("mn_address_validation.json","checked_at_utc",72,"gis_address_matched"),
         "mngeo_aerial":("mngeo_aerial_evidence.json","generated_at_utc",72,"remote_image_verified"),
         "property_values":("live_property_enrichment.json","generated_utc",36,None),
         "regional_permits":("regional_residential_permit_matches.json","checked_at_utc",72,"matches_pending_review"),
         "municipal_permits":("permit_match_review.json","generated_at_utc",168,None),
         "categories":("property_category_intelligence.json","created_utc",72,"count"),
         "integrity":("pipeline_integrity.json","checked_at_utc",36,"records")}
RECOMMEND={"parcels":"Repair official GIS parcel import and dedupe by county PIN",
"gis_geometry":"Review official Eagan parcel-center subdivision intersections",
"mn_addresses":"Investigate GIS address service; USPS requires separate OAuth credentials",
"mngeo_aerial":"Fix official WMS GetMap source and validate returned JPEG bytes",
"property_values":"Reconcile parcel ID and official city valuation layer",
"regional_permits":"Review regional residential permit source and address matches",
"municipal_permits":"Obtain authorized City of Eagan permit export, do not evade 403",
"categories":"Rebuild roofing/tree/driveway evidence cards without inferred damage",
"integrity":"BLOCK score promotion and investigate cross-file integrity errors"}
def read(f):
 try:return json.loads(f.read_text(encoding="utf-8"))
 except (OSError,ValueError):return {}
def ageh(value,now):
 try:
  t=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
  if t.tzinfo is None:t=t.replace(tzinfo=dt.timezone.utc)
  return max(0,round((now-t).total_seconds()/3600,2))
 except (TypeError,ValueError):return None
def run(d):
 now=dt.datetime.now(dt.timezone.utc);states=[];proposals=[]
 for name,(file,date,maxage,field) in SOURCES.items():
  f=d/file;payload=read(f)
  age=ageh(payload.get(date),now)
  status="MISSING" if not f.exists() else "UNKNOWN_TIMESTAMP" if age is None else "STALE" if age>maxage else "CURRENT"
  count=payload.get(field,0) if field else len(payload.get("records",[]) or payload.get("properties",[]) or [])
  if name=="property_values":count=payload.get("counts",{}).get("assessments_sourced",0)
  if name=="gis_geometry":count=payload.get("counts",{}).get("OFFICIAL_CENTER_IN_KINGS_WOOD_PLAT",0)
  errs=payload.get("source_errors",[]) or payload.get("errors",[])
  if name=="integrity" and payload and payload.get("pass") is not True:errs=["Integrity gate failed"]
  if name=="mngeo_aerial" and payload.get("network_probed") is False:status="NOT_PROBED"
  if status=="CURRENT" and errs:status="SOURCE_ISSUE"
  row={"source":name,"file":file,"status":status,"age_hours":age,"max_age_hours":maxage,"evidence_count":count,"errors":errs}
  states.append(row)
  if status!="CURRENT" or not count:
   rec={"decision_id":"UPG-"+hashlib.sha256(name.encode()).hexdigest()[:12],
    "source":name,"priority":"CRITICAL" if name=="integrity" else "HIGH" if name in ("parcels","gis_geometry","municipal_permits","mngeo_aerial") else "MEDIUM",
    "proposed_action":RECOMMEND[name],"reason":status+"; current source-backed count="+str(count),
    "status":"NEEDS_HUMAN_REVIEW","approved":False,
    "requires":["source rights","automated tests","human sign-off"]}
   proposals.append(rec)
 report={"generated_at_utc":now.isoformat(),"engine":"GateKeeper Source Pulse v1","source_count":len(states),"healthy_sources":sum(x["status"]=="CURRENT" for x in states),"sources":states,"upgrade_count":len(proposals),"upgrades_for_human_review":proposals,"no_autonomous_approval":True,"no_unverified_condition_scores":True,"note":"Freshness and data acquisition do not establish roof damage or USPS deliverability"}
 d.mkdir(parents=True,exist_ok=True)
 (d/"gatekeeper_pulse.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
 (d/"human_upgrade_decisions.json").write_text(json.dumps({"updated_at_utc":report["generated_at_utc"],"decisions":proposals,"approval_policy":"Human review mandatory; proposals are NOT approvals"},indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"sources":len(states),"current":report["healthy_sources"],"proposals":len(proposals)}))
 return report
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--data-dir",default="evidence/data");args=p.parse_args();run(pathlib.Path(args.data_dir))
