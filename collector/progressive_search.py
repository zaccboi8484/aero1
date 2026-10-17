#!/usr/bin/env python3
"""AeroLeadAI progressive search controller — source-backed, no fabricated findings.
Builds deterministic per-parcel search tasks and GateKeeper outcomes from existing
official manifests. Tasks marked PENDING are not searches claimed as performed.
"""
import csv,hashlib,json,pathlib,datetime as dt
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
results=[]
for p in parcels:
 oid=str(p.get("parcel_objectid",""));pin=str(p.get("county_pin",""))
 address=p.get("address","")
 if not oid or not pin or not address:continue
 image=imagery.get(oid,{})
 source=p.get("source_record_url","")
 genuine=source.startswith("https://") and p.get("verification_status")=="UNVERIFIED"
 plat=str(p.get("plat_name","")).upper()
 recognized=bool(plat and any(plat.replace("ADD","ADDITION") in n or n.replace("ADDITION","ADD") in plat for n in plats))
 permit_records=matches.get(oid,[])
 checks=[
  step("parcel","MetroGIS ArcGIS","SOURCE_RECORDED" if genuine else "UNVERIFIED","Official parcel ID and address present" if genuine else "Missing primary GIS provenance","Validate parcel against Eagan plat geometry"),
  step("subdivision","Eagan subdivision GIS","PLAT_NAME_MATCH_PENDING_SPATIAL" if recognized else "PENDING","City plat catalog checked; polygon membership not certified","Intersect parcel geometry with official plat geometry"),
  step("permit","Eagan public permit export","MATCH_PENDING_REVIEW" if permit_records else "SOURCE_ACCESS_BLOCKED","Potential matches: "+str(len(permit_records)) if permit_records else "Permit portal returned HTTP 403; no property-specific search export in evidence store","Use authorized city export; reconcile permit number, address and source date"),
  step("imagery","Dakota County GIS ImageServer","SOURCE_IMAGE_DOWNLOADED_UNVERIFIED" if image.get("status")=="DOWNLOADED" else ("FETCH_FAILED" if image.get("status")=="FAILED" else "NOT_ATTEMPTED"),image.get("reason","No image hash/bytes recorded"),"Resolve correct ImageServer response and rights; retry only official service"),
  step("value","County assessment / Eagan property GIS","SOURCE_RECORDED_PENDING_REVIEW" if values.get(oid,{}).get("gatekeeper")=="SOURCE_RECORDED" else "NOT_RETRIEVED","Actual city GIS value: "+str(values[oid]["amount_usd"])+" (assessment year unavailable)" if values.get(oid,{}).get("gatekeeper")=="SOURCE_RECORDED" else "Official value not unambiguously matched","Check assessment year and reviewer before financial conclusions"),
  step("gatekeeper","GateKeeper coordinator","AWAITING_EVIDENCE","No evidence-reviewed roof, driveway or tree conclusion","Require source corroboration and human review before findings")
 ]
 critical=all(s["status"] not in ("SOURCE_ACCESS_BLOCKED","NOT_ATTEMPTED","FETCH_FAILED","NOT_RETRIEVED","AWAITING_EVIDENCE","PENDING","UNVERIFIED") for s in checks)
 score={"mindex":None,"property_value":None,"status":"NOT_SCORED","reason":"Insufficient reviewed evidence"}
 results.append({"territory":"001","parcel_objectid":oid,"county_pin":pin,"address":address,"plat_name":p.get("plat_name",""),"gis_url":source,"street_view":"OUTBOUND_LINK_ONLY","checks":checks,"score":score,"gatekeeper":"INCOMPLETE","completion":"COMPLETE" if critical else "OPEN"})
counts={s:sum(any(c["status"]==s for c in r["checks"]) for r in results) for s in ["SOURCE_RECORDED","SOURCE_ACCESS_BLOCKED","FETCH_FAILED","MATCH_PENDING_REVIEW","NOT_RETRIEVED"]}
output={"generated_at_utc":NOW,"policy":"real evidence only; no inferred damage","territory":"Kings Wood, Eagan","properties":results,"totals":{"property_records":len(results),"completed":sum(r["completion"]=="COMPLETE" for r in results),"mindex_scored":0,"checks":counts},"progression":{"phase":"SEED_EVIDENCE_COLLECTION","next_ring":"LOCKED_PENDING_TERRITORY_001_VALIDATION","order":["roofing","cracked_driveways","potentially_dangerous_trees","siding","gutters"],"ring_rule":"Buffer official territory boundary outward; never expand solely by street-name similarity; collect as leads but do not mark completed without evidence"}}
DATA.mkdir(parents=True,exist_ok=True)
(DATA/"progressive_search_status.json").write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
print(json.dumps(output["totals"],indent=2))
