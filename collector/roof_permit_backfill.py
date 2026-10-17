#!/usr/bin/env python3
"""GateKeeper 2025 re-roof permit backfill and auditable outreach queue.

Input: official Eagan municipal CSV export, where available; optional matching
of pre-existing reviewed municipal permit evidence. This never scrapes past a
403 and never infers that an absent match means no permit exists.

Only a completed 2025 roofing permit with a unique exact address/PIN match,
source ID, and named reviewer can LOWER roof outreach priority. Neither a
permit nor the priority score verifies current property condition.
"""
import argparse, csv, datetime as dt, hashlib, json, pathlib, re
from collections import defaultdict

YEAR=2025
ROOF_WORDS=("roof", "reroof", "re-roof", "shingle", "roofing")
FINAL_WORDS=("final", "complete", "closed", "issued", "approved")
ALIASES={
 "address":("address","property_address","site_address","street_address","job_address"),
 "pin":("parcel_id","pin","county_pin","parcel_number","taxpin"),
 "id":("permit_number","permit_id","record_id","number"),
 "type":("permit_type","work_type","description","project_description","work_description"),
 "date":("final_date","issued_date","issue_date","completed_date","date","permit_date"),
 "status":("permit_status","status","final_status"),
 "source":("source_url","permit_url","record_url"),
 "reviewer":("reviewer_id","reviewed_by","verified_by"),
 "reviewed":("reviewed_at","review_date"),
 "verification":("review_status","verification_status")
}
def get(d,key):
 for name in ALIASES[key]:
  if str(d.get(name,"")).strip():return str(d[name]).strip()
 return ""
def normalize(s):
 s=re.sub(r"[^A-Z0-9 ]"," ",str(s or "").upper())
 for before,after in (("ROAD","RD"),("LANE","LN"),("COURT","CT"),("DRIVE","DR"),("STREET","ST"),("AVENUE","AVE")):
  s=re.sub(r"\b"+before+r"\b",after,s)
 return " ".join(s.split())
def street(s):return normalize(str(s or "").split(",")[0])
def date(s):
 raw=str(s or "").strip()
 for fmt in ("%Y-%m-%d","%m/%d/%Y","%m-%d-%Y","%Y-%m-%dT%H:%M:%S","%Y/%m/%d"):
  try:return dt.datetime.strptime(raw[:19] if "T" in raw and fmt.endswith("%S") else raw,fmt).date()
  except ValueError:pass
 return None
def official_roof(row):
 kind=get(row,"type").lower();status=get(row,"status").lower()
 # Do not equate general new construction with a roofing permit.
 return any(x in kind for x in ROOF_WORDS) and any(x in status for x in FINAL_WORDS) and bool(get(row,"id"))
def reviewed(row):
 return (get(row,"verification").upper() in ("REVIEWED","VERIFIED","APPROVED") and
  bool(get(row,"reviewer")) and date(get(row,"reviewed")) is not None)
def readjson(d,name):
 try:return json.loads((d/name).read_text(encoding="utf-8"))
 except (OSError,ValueError):return {}
def rowscsv(path):
 if not path or not path.is_file():return []
 with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def build(d,permit_csv=None):
 parcels=rowscsv(d/"kingswood_parcel_candidates.csv")
 expanded=readjson(d,"outward_ring_candidates.json").get("ring_candidates",[])
 candidates=parcels+expanded
 bypin={};byaddress=defaultdict(list)
 for p in candidates:
  pin=str(p.get("county_pin") or "");addr=street(p.get("address"))
  if not pin or not addr or pin in bypin:continue
  bypin[pin]=p;byaddress[addr].append(p)
 # Existing permit_match_review.json is evidence only if it actually has unique,
 # independently reviewed municipal records; no self-approval.
 existing=readjson(d,"permit_match_review.json").get("records",[])
 source_rows=rowscsv(permit_csv)+existing
 eligible=defaultdict(list);rejected=[]
 for record in source_rows:
  if not official_roof(record):continue
  occurred=date(get(record,"date"))
  if not occurred or occurred.year!=YEAR:continue
  source=get(record,"source");p=get(record,"pin");address=street(get(record,"address"))
  candidate=bypin.get(p) if p else None
  if candidate and address and street(candidate["address"])!=address:
   rejected.append({"permit_id":get(record,"id"),"reason":"PIN_ADDRESS_CONTRADICTION"});continue
  if not candidate and address:
   matching=byaddress.get(address,[])
   if len(matching)==1:candidate=matching[0]
  if candidate is None:
   rejected.append({"permit_id":get(record,"id"),"reason":"AMBIGUOUS_OR_UNMATCHED_ADDRESS"});continue
  # Official issuer source URL + actual human review are necessary to reduce priority.
  source_ok=source.startswith("https://") and ("eagan" in source.lower() or "mn.gov" in source.lower())
  isreviewed=reviewed(record) and source_ok
  event={"permit_id":get(record,"id"),"permit_date":occurred.isoformat(),
   "record_status":get(record,"status"),"type":get(record,"type"),
   "source_url":source or None,"review_status":"VERIFIED_RECENT_REROOF" if isreviewed else "MATCH_PENDING_REVIEW",
   "reviewer_id":get(record,"reviewer") if isreviewed else None,
   "evidence_sha256":hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()}
  eligible[str(candidate["county_pin"])].append(event)
 score_data=readjson(d,"roof_evidence_scores.json").get("records",[])
 prior={str(x.get("county_pin")):x for x in score_data}
 ordered=[]
 for pin,p in bypin.items():
  base=prior.get(pin,{}).get("review",{}).get("data_review_priority")
  if not isinstance(base,(int,float)):base=50
  events=eligible.get(pin,[])
  validated=[x for x in events if x["review_status"]=="VERIFIED_RECENT_REROOF"]
  # This score controls roofing outreach/review order, NOT hail/damage/Mindex.
  adjustment=-45 if validated else 0
  next_score=max(0,min(100,int(base)+adjustment))
  ordered.append({"parcel_objectid":str(p.get("parcel_objectid")),"county_pin":pin,
   "address":p.get("address"),"ring":p.get("ring","territory_001"),
   "base_data_priority":int(base),"roofing_outreach_priority":next_score,
   "priority_adjustment":adjustment,"last_year":YEAR,"matched_roof_permits":events,
   "recent_roof_verified":bool(validated),"search_status":"VERIFIED_2025_REROOF" if validated else
    ("PENDING_PERMIT_REVIEW" if events else "NO_MATCH_FROM_AVAILABLE_EVIDENCE"),
   "condition_status":"UNKNOWN","priority_is_damage_score":False})
 ordered.sort(key=lambda r:(-r["roofing_outreach_priority"],r["county_pin"]))
 payload={"generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"scope":"AeroLeadAI only, no legacy bulk lead or image imports",
 "year":YEAR,"properties":len(ordered),"reviewed_recent_reroofs":sum(x["recent_roof_verified"] for x in ordered),
 "source_export_rows":len(source_rows),"rejected_matches":rejected,
 "municipal_export_connected":bool(permit_csv and permit_csv.is_file()),
 "warning":"Absent permit evidence is UNKNOWN. Only verified final 2025 reroof permits lower outreach priority. No property damage or replacement finding is inferred.",
 "records":ordered}
 d.mkdir(parents=True,exist_ok=True)
 (d/"roof_permit_backfill_2025.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
 return payload
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--data-dir",type=pathlib.Path,default=pathlib.Path("evidence/data"));p.add_argument("--official-csv",type=pathlib.Path,default=None)
 args=p.parse_args();r=build(args.data_dir,args.official_csv)
 print(json.dumps({k:r[k] for k in ("properties","source_export_rows","reviewed_recent_reroofs","municipal_export_connected")}))