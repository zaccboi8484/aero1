#!/usr/bin/env python3
"""Automated integrity gate for AeroLeadAI's 60 source-backed cards.
Checks record identity, cross-file joins, evidence status, audit integrity and
the three service categories. Passing means the files are consistent, NOT that
permits/imagery/condition are verified.
"""
import csv,hashlib,json,pathlib,sys
from datetime import datetime,timezone
DIR=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
def load(name):
 with (DIR/name).open(encoding="utf-8") as f:return json.load(f)
with (DIR/"kingswood_parcel_candidates.csv").open(newline="",encoding="utf-8-sig") as f:rows=list(csv.DictReader(f))
progress=load("progressive_search_status.json")
categories=load("property_category_intelligence.json")
enrich=load("live_property_enrichment.json")
audit=load("gatekeeper_property_audit.json")
geo=load("subdivision_geometry_checks.json")
images=load("imagery_downloads.json")
issues=[]
def check(ok,message):
 if not ok:issues.append(message)
ids=[str(r.get("parcel_objectid") or "") for r in rows]
pins=[str(r.get("county_pin") or "") for r in rows]
check(len(ids)==60,f"Expected 60 real property rows; got {len(ids)}")
check(len(set(ids))==len(ids),"Duplicate GIS record IDs")
check(len(set(pins))==len(pins),"Duplicate county PINs")
def matched_records(items,name):
 d={str(r.get("parcel_objectid") or ""):r for r in items}
 check(len(items)==len(d),f"Duplicate objects in {name}")
 check(set(d)==set(ids),f"Parcel IDs out of sync in {name}")
 return d
pr=matched_records(progress.get("properties",[]),"progress")
cat=matched_records(categories.get("records",[]),"categories")
vals=matched_records(enrich.get("records",[]),"enrichment")
au=matched_records(audit.get("audit",[]),"audit")
ge=matched_records(geo.get("records",[]),"city geometry")
image={str(x.get("parcel_objectid") or ""):x for x in images.get("records",[])}
check(len(image)==len(images.get("records",[])),"Duplicate imagery attempts")
check(len(image)==len(ids),"Image attempt count differs from property count")
for row in rows:
 oid=str(row.get("parcel_objectid"));pin=str(row.get("county_pin"))
 p=pr.get(oid,{});c=cat.get(oid,{});v=vals.get(oid,{});a=au.get(oid,{});g=ge.get(oid,{})
 check(p.get("county_pin")==pin,f"{oid}: mismatched PIN in search audit")
 check(c.get("county_pin")==pin,f"{oid}: mismatched PIN in categories")
 check(v.get("county_pin")==pin,f"{oid}: mismatched PIN in valuations")
 check(g.get("county_pin")==pin,f"{oid}: mismatched PIN in city GIS spatial results")
 check(c.get("address")==row.get("address"),f"{oid}: inconsistent address")
 check(p.get("completion")=="OPEN" or p.get("gatekeeper")=="COMPLETE",f"{oid}: unsupported completion state")
 if p.get("score",{}).get("mindex") is not None:
  check(p.get("gatekeeper")=="COMPLETE",f"{oid}: scored without completed review")
 for key in ("roofing","tree_service","cracked_driveway"):
  k=c.get("categories",{}).get(key,{})
  check(bool(k),f"{oid}: category {key} absent")
  if k.get("finding") not in ("UNKNOWN",None):
   check(k.get("reviewer") and k.get("reviewed_at") and k.get("evidence_ids"),f"{oid}: unreviewed defect inference in {key}")
  if not (image.get(oid,{}).get("status")=="DOWNLOADED" and image.get(oid,{}).get("sha256")):
   check(k.get("finding") in ("UNKNOWN",None),f"{oid}: image defect asserted without image")
 if a:
  digest=a.get("sha256")
  payload={k:value for k,value in a.items() if k!="sha256"}
  check(hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()==digest,f"{oid}: audit checksum mismatch")
  check(a.get("identity")==p.get("identity_status"),f"{oid}: audit identity mismatch")
 if g.get("status")=="OFFICIAL_CENTER_IN_KINGS_WOOD_PLAT":
  check(bool(g.get("matched_plats")),f"{oid}: GIS spatial confirmation missing polygon record")
 check(str(row.get("source_record_url") or "").startswith("https://"),f"{oid}: missing original GIS source URL")
result={"checked_at_utc":datetime.now(timezone.utc).isoformat(),"pass":not issues,
 "records":len(ids),"cross_file_checks":["parcel","category","valuation","audit","GIS_geometry","imagery"],
 "issues":issues[:100],"source_verified_property_condition_count":sum(p.get("gatekeeper")=="COMPLETE" for p in pr.values()),
 "warning":"Passing checks source joins and evidence gates, not 60 complete property investigations."}
(DIR/"pipeline_integrity.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k!="issues"},indent=2))
if issues:
 print("Integrity failures:\n"+"\n".join(issues[:30]),file=sys.stderr)
 sys.exit(1)
