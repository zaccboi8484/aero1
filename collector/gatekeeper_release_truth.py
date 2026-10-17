#!/usr/bin/env python3
"""GateKeeper release truth contract. Ingest published evidence, never infer completion
from GitHub Actions success. Produces actionable reviewed/human-decision report.
"""
import csv,datetime as dt,json,pathlib
D=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
def read(name):
 try:return json.loads((D/name).read_text(encoding="utf-8"))
 except (FileNotFoundError,ValueError):return {}
def main():
 p=read("progressive_search_status.json");integrity=read("pipeline_integrity.json")
 img=read("imagery_source_probe.json");regional=read("regional_residential_permit_matches.json")
 mnimg=read("mngeo_aerial_evidence.json");address=read("mn_address_validation.json")
 v=read("live_property_enrichment.json");geo=read("subdivision_geometry_checks.json")
 tasks=read("search_retry_queue.json")
 eagan_exports=read("municipal_permit_export_audit.json")
 totals=p.get("totals",{})
 parcel_count=int(totals.get("property_records",0))
 def gate(key,title,done,target,evidence,blocking):
  status="VERIFIED" if target>0 and done>=target else "PARTIAL" if done>0 else "BLOCKED"
  return {"id":key,"name":title,"status":status,"done":done,"target":target,"evidence_file":evidence,"blocking":blocking}
 gates=[
 gate("01_PARCEL","Official GIS parcel identity",totals.get("gis_identities_confirmed",0),parcel_count,"progressive_search_status.json","GIS identity not found"),
 gate("02_PLAT","City subdivision point-in-polygon",totals.get("gis_center_point_in_kings_wood",0),parcel_count,"subdivision_geometry_checks.json","Official city polygon intersection incomplete"),
 gate("03_ADDRESS","Minnesota GIS address match",address.get("gis_address_matched",0),parcel_count,"mn_address_validation.json","No source-matched address-point report; USPS OAuth is separate"),
 gate("04_VALUES","Official source-matched property valuations",totals.get("city_values_source_matched",0),parcel_count,"live_property_enrichment.json","Assessment year and reviewer still require confirmation"),
 gate("05_MUNICIPAL_PERMITS","Eagan municipal permits reviewed",sum(1 for x in p.get("properties",[]) if any(c.get("search_id")=="permit" and c.get("status")=="REVIEWED" for c in x.get("checks",[]))),parcel_count,"permit_match_review.json","Municipal portal access denied; no fully reviewed authorized records"),
 gate("06_REGIONAL_PERMITS","Regional permit candidate matching",regional.get("matched_properties",0),parcel_count,"regional_residential_permit_matches.json","Regional source does not substitute for municipal reroof history"),
 gate("07_IMAGERY","Valid image response per parcel",max(img.get("remote_jpegs_verified",0),mnimg.get("remote_image_verified",0)),parcel_count,"imagery_source_probe.json / mngeo_aerial_evidence.json","Source imagery missing or failed; illustrative imagery is not evidence"),
 gate("08_CONDITIONS","Reviewed roof/tree/driveway evidence",sum(1 for x in p.get("properties",[]) if x.get("evidence_status")=="COMPLETE"),parcel_count,"property_category_intelligence.json","Need suitable imagery, permits or dated reviewer findings"),
 gate("09_MINDEX","Evidence-supported Mindex",totals.get("mindex_scored",0),parcel_count,"progressive_search_status.json","Never issue unreviewed scores"),
 gate("10_INTEGRITY","Pipeline cross-file integrity",1 if integrity.get("pass") is True else 0,1,"pipeline_integrity.json","Cross-file integrity checks not passed")
 ]
 stale=[]
 try:
  created=dt.datetime.fromisoformat(p["generated_at_utc"].replace("Z","+00:00"))
  age=(dt.datetime.now(dt.timezone.utc)-created).total_seconds()/3600
  if age>48:stale.append("Progress report exceeds 48 hours")
 except (KeyError,TypeError,ValueError):stale.append("No timestamped property progression")
 decisions=[]
 for x in gates:
  if x["status"]=="VERIFIED":continue
  decisions.append({"gate":x["id"],"status":"NEEDS_HUMAN_REVIEW","approved":False,"priority":"HIGH" if x["id"] in ("05_MUNICIPAL_PERMITS","07_IMAGERY","08_CONDITIONS") else "MEDIUM","reason":x["blocking"],"evidence":x["evidence_file"]})
 out={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
 "product":"AeroLeadAI","assistant":"Embedded GateKeeper","release_certified":all(x["status"]=="VERIFIED" for x in gates) and not stale,
 "meaning":"Each gate requires source evidence. PASS of an internal test never certifies physical condition.",
 "pipeline_integrity_pass":integrity.get("pass") is True,
 "municipal_export_review":{"input_report_rows":eagan_exports.get("total_source_rows",0),"matched_permit_events":eagan_exports.get("matched_permit_events",0),"properties_with_matching_reports":eagan_exports.get("properties_with_matches",0),"explicit_2025_roof_candidates":eagan_exports.get("properties_with_2025_roof_candidates",0),"documents_reviewed":0,"issuer_live_recheck":False,"statement":"Owner-provided Eagan CSV reports: matches collected but physical roof/permit issue details require document review"},"property_records":parcel_count,
 "fully_reviewed_properties":totals.get("completed",0),"pending_search_tasks":tasks.get("count"),
 "gates":gates,"stale_warnings":stale,"decisions_for_human":decisions,
 "external_original_site":{"status":"NOT_VERIFIED_FROM_THIS_REPOSITORY","note":"Original Twin Cities application may be an entirely separate project; do not infer absence."}}
 D.mkdir(parents=True,exist_ok=True)
 (D/"gatekeeper_release_truth.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"release_certified":out["release_certified"],"verified_gates":sum(x["status"]=="VERIFIED" for x in gates),"partial_gates":sum(x["status"]=="PARTIAL" for x in gates),"property_count":parcel_count,"fully_reviewed":out["fully_reviewed_properties"]}))
 return out
if __name__=="__main__":main()
