#!/usr/bin/env python3
"""Produce a deterministic, jurisdiction-aware permit investigation queue.
Real county GIS candidate input only; rows are *research tasks*, not permit results.

Usage:
  python collector/route_permit_research.py
  python collector/route_permit_research.py --parcels /path/to/burnsville-parcels.csv --jurisdiction burnsville --out evidence/data/burnsville_permit_tasks.json

Exported Eagan/Burnsville reports are then fed to match_permits.py for review.
"""
import argparse,csv,datetime,json,pathlib,re,urllib.parse,hashlib
ROOT=pathlib.Path(__file__).resolve().parent.parent
REGISTRY=ROOT/"evidence/config/jurisdictions.json"
DEFAULT=ROOT/"evidence/data/kingswood_parcel_candidates.csv"
def normalized_address(address):
 return re.sub(r"\s+"," ",str(address or "").strip()).upper()
def tasks_for(parcels,jurisdiction,registry):
 route=next((x for x in registry["jurisdictions"] if x["id"]==jurisdiction),None)
 if not route or jurisdiction=="dakota_county":raise ValueError("Building-permit research must route to city jurisdiction; county records handled separately")
 seen=set();out=[]
 for row in parcels:
  address=str(row.get("address") or "").strip()
  parcel=str(row.get("county_pin") or "").strip()
  objectid=str(row.get("parcel_objectid") or "").strip()
  if not address or not objectid:continue
  if jurisdiction not in normalized_address(address).lower():
   # Do not misroute Eagan property to Burnsville.
   continue
  uid=hashlib.sha256((jurisdiction+"|"+objectid+"|"+normalized_address(address)).encode()).hexdigest()[:24]
  if uid in seen:continue
  seen.add(uid)
  out.append({
   "id":uid,"jurisdiction":jurisdiction,"county":"Dakota","address":address,
   "parcel_objectid":objectid,"county_pin":parcel,"source_parcel_url":row.get("source_record_url"),
   "research_status":"NOT_SEARCHED","permit_matches":[],"verified_permits":0,"source_documents":[],
   "source_portal_url":route.get("permit_search") or route.get("permit_info"),
   "public_reports_url":route.get("public_reports") or route.get("commercial_reports"),
   "planned_steps":["Public city address/permit search","Official bulk permit report address match","Request historical record packets if not publicly downloadable","Review permit number, type, issue date and source before acceptance"],
   "evidence_status":"UNKNOWN","priority_classes":["roofing","driveway","trees"],
   "notes":"Research task; no claim that permit exists or does not exist"
  })
 return out
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--parcels",type=pathlib.Path,default=DEFAULT)
 p.add_argument("--jurisdiction",choices=["eagan","burnsville"],default="eagan")
 p.add_argument("--out",type=pathlib.Path,default=None)
 a=p.parse_args()
 if not a.parcels.exists():p.error("Real parcel CSV required; collector will not invent addresses")
 rows=list(csv.DictReader(a.parcels.open(encoding="utf-8-sig",newline="")))
 registry=json.loads(REGISTRY.read_text())
 tasks=tasks_for(rows,a.jurisdiction,registry)
 out=a.out or ROOT/"evidence/data"/(a.jurisdiction+"_permit_research_tasks.json")
 out.parent.mkdir(parents=True,exist_ok=True)
 manifest={"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"jurisdiction":a.jurisdiction,
 "input_parcels":len(rows),"tasks":len(tasks),"completed_permit_searches":0,"confirmed_permit_matches":0,
 "type":"RESEARCH_QUEUE_NOT_FINDINGS","source_registry":"evidence/config/jurisdictions.json","records":tasks}
 out.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
 print(f"Generated {len(tasks)} genuine {a.jurisdiction} jurisdictional research tasks at {out}")
if __name__=="__main__":main()
