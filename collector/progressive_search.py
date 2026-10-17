#!/usr/bin/env python3
"""AeroLeadAI progressive search controller — source-backed, no fabricated findings.
Builds deterministic per-parcel search tasks and GateKeeper outcomes from existing
official manifests. Tasks marked PENDING are not searches claimed as performed.
"""
import csv,hashlib,json,pathlib,datetime as dt,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/"evidence"/"data"
NOW=dt.datetime.now(dt.timezone.utc).isoformat()
def read_json(name,default):
 try:return json.loads((DATA/name).read_text(encoding="utf-8"))
 except (FileNotFoundError,ValueError):return default
def rows(name):
 try:
  with (DATA/name).open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
 except FileNotFoundError:return []
def step(key,source,status,detail,next_action):
 return {"search_id":key,"source":source,"status":status,"detail":detail,"next_action":next_action}
parcels=rows("kingswood_parcel_candidates.csv")
discovery=read_json("official_source_discovery.json",{})
download=read_json("imagery_downloads.json",{})
enrichment=read_json("live_property_enrichment.json",{})
values={str(x.get("parcel_objectid")):x.get("valuation",{}) for x in enrichment.get("records",[])}
permit=read_json("permit_match_review.json",{})
permitted=permit.get("records",[]) if isinstance(permit,dict) else []
imagery={str(r.get("parcel_objectid")):r for r in download.get("records",[])}
matches={}
for p in permitted:
 if p.get("match_status")=="EXACT_ADDRESS_PENDING_REVIEW":
  matches.setdefault(str(p.get("parcel_objectid")),[]).append(p)
plats={str(x.get("attributes",{}).get("PLATNAME","")).upper() for x in discovery.get("subdivision_candidates",[])}
DATA.mkdir(parents=True,exist_ok=True)
results=[]
for p in parcels:
 oid=str(p.get("parcel_objectid",""));pin=str(p.get("county_pin",""))
 address=p.get("address","")
 if not oid or not pin or not address:continue
 image=imagery.get(oid,{})
 source=p.get("source_record_url","")
 genuine=source.startswith("https://") and p.get("verification_status")=="UNVERIFIED"
 plat=str(p.get("plat_name","")).upper()
 normalized=lambda v:re.sub(r"\\bADD\\b","ADDITION",str(v).upper()).strip()
 recognized=bool(plat and normalized(plat) in {normalized(n) for n in plats})
 permit_records=matches.get(oid,[])
 checks=[
  step("parcel","MetroGIS ArcGIS","SOURCE_RECORDED" if genuine else "UNVERIFIED","Official parcel ID and address present" if genuine else "Missing primary GIS provenance","Validate parcel against Eagan plat geometry"),
  step("subdivision","Eagan subdivision GIS","PLAT_NAME_MATCH_PENDING_SPATIAL" if recognized else "PENDING","City plat catalog checked; polygon membership not certified","Intersect parcel geometry with official plat geometry"),
  step("permit","Eagan public permit export","MATCH_PENDING_REVIEW" if permit_records else "SOURCE_ACCESS_BLOCKED","Potential matches: "+str(len(permit_records)) if permit_records else "Permit portal returned HTTP 403; no property-specific search export in evidence store","Use authorized city export; reconcile permit number, address and source date"),
  step("imagery","Dakota County GIS ImageServer","SOURCE_IMAGE_DOWNLOADED_UNVERIFIED" if image.get("status")=="DOWNLOADED" else ("FETCH_FAILED" if image.get("status")=="FAILED" else "NOT_ATTEMPTED"),image.get("reason","No image hash/bytes recorded"),"Resolve correct ImageServer response and rights; retry only official service"),
  step("value","County assessment / Eagan property GIS","SOURCE_RECORDED_PENDING_REVIEW" if values.get(oid,{}).get("gatekeeper")=="SOURCE_RECORDED" else "NOT_RETRIEVED","Actual city GIS value: "+str(values[oid]["amount_usd"])+" (assessment year unavailable)" if values.get(oid,{}).get("gatekeeper")=="SOURCE_RECORDED" else "Official value not unambiguously matched","Check assessment year and reviewer before financial conclusions"),
  step("gatekeeper","GateKeeper coordinator","AWAITING_EVIDENCE","No evidence-reviewed roof, driveway or tree conclusion","Require source corroboration and human review before findings")
 ]
 identity="OFFICIAL_GIS_SOURCE_CONFIRMED" if genuine else "IDENTITY_UNVERIFIED"
 subdivision="OFFICIAL_PLAT_NAME_CORROBORATED" if recognized else "SUBDIVISION_NOT_CONFIRMED"
 valuation="CITY_PIN_ADDRESS_SOURCE_MATCHED_PENDING_REVIEW" if values.get(oid,{}).get("gatekeeper")=="SOURCE_RECORDED" else "NOT_MATCHED"
 critical=False # An evidence-complete property requires actual permit/imagery review; no shortcut.
 score={"mindex":None,"property_value":None,"status":"NOT_SCORED","reason":"Insufficient reviewed evidence"}
 results.append({"territory":"001","parcel_objectid":oid,"county_pin":pin,"address":address,"plat_name":p.get("plat_name",""),"gis_url":source,"street_view":"OUTBOUND_LINK_ONLY","identity_status":identity,"subdivision_status":subdivision,"valuation_status":valuation,"evidence_status":"NOT_COMPLETE","checks":checks,"score":score,"gatekeeper":"INCOMPLETE","completion":"COMPLETE" if critical else "OPEN"})
counts={s:sum(any(c["status"]==s for c in r["checks"]) for r in results) for s in ["SOURCE_RECORDED","SOURCE_ACCESS_BLOCKED","FETCH_FAILED","MATCH_PENDING_REVIEW","NOT_RETRIEVED","SOURCE_RECORDED_PENDING_REVIEW"]}
# Real, re-runnable search tasks. Blocked access is not reclassified as success.
tasks=[]
priority={"subdivision":1,"value":2,"permit":3,"imagery":4,"gatekeeper":5}
for rec in results:
 for check in rec["checks"]:
  if check["search_id"]=="parcel" and check["status"]=="SOURCE_RECORDED":continue
  if check["search_id"]=="value" and check["status"]=="SOURCE_RECORDED_PENDING_REVIEW":continue
  tasks.append({"parcel_objectid":rec["parcel_objectid"],"county_pin":rec["county_pin"],"address":rec["address"],"search_type":check["search_id"],"priority":priority.get(check["search_id"],9),"previous_status":check["status"],"next_action":check["next_action"],"attempted":check["status"] in ["FETCH_FAILED","SOURCE_ACCESS_BLOCKED"],"gatekeeper":"PENDING_OR_BLOCKED"})
tasks.sort(key=lambda x:(x["priority"],x["parcel_objectid"]))
audit_rows=[{"parcel_objectid":r["parcel_objectid"],"identity":r["identity_status"],"subdivision":r["subdivision_status"],"valuation":r["valuation_status"],"evidence":r["evidence_status"],"checks":{v["search_id"]:v["status"] for v in r["checks"]}} for r in results]
for row in audit_rows:row["sha256"]=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()
(DATA/"gatekeeper_property_audit.json").write_text(json.dumps({"generated_at_utc":NOW,"audit":audit_rows},indent=2))
(DATA/"search_retry_queue.json").write_text(json.dumps({"generated_at_utc":NOW,"tasks":tasks,"count":len(tasks),"warning":"These are pending/blocked search tasks, not successfully executed crawls."},indent=2))

output={"generated_at_utc":NOW,"policy":"real evidence only; no inferred damage","territory":"Kings Wood, Eagan","properties":results,"totals":{"property_records":len(results),"gis_identities_confirmed":sum(r["identity_status"]=="OFFICIAL_GIS_SOURCE_CONFIRMED" for r in results),"plat_names_corroborated":sum(r["subdivision_status"]=="OFFICIAL_PLAT_NAME_CORROBORATED" for r in results),"city_values_source_matched":sum(r["valuation_status"]=="CITY_PIN_ADDRESS_SOURCE_MATCHED_PENDING_REVIEW" for r in results),"retry_tasks":len(tasks),"completed":sum(r["completion"]=="COMPLETE" for r in results),"mindex_scored":0,"checks":counts},"progression":{"phase":"SEED_EVIDENCE_COLLECTION","next_ring":"LOCKED_PENDING_TERRITORY_001_VALIDATION","order":["roofing","cracked_driveways","potentially_dangerous_trees","siding","gutters"],"ring_rule":"Buffer official territory boundary outward; never expand solely by street-name similarity; collect as leads but do not mark completed without evidence"}}
DATA.mkdir(parents=True,exist_ok=True)
(DATA/"progressive_search_status.json").write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
print(json.dumps(output["totals"],indent=2))
