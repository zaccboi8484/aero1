#!/usr/bin/env python3
"""Import owner-supplied City of Eagan public CSV reports into AeroLeadAI.
Reusable, duplicate-safe, exact-address/PIN matches. Does not crawl past 403.
Outputs only permit identifiers and classifications, never applicant/owner names.
"""
import argparse,csv,datetime,json,hashlib,pathlib,re
from collections import defaultdict
D=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
def norm(v):
 s=str(v or "").split(",",1)[0].upper()
 for a,b in (("ROAD","RD"),("LANE","LN"),("COURT","CT"),("AVENUE","AVE"),("DRIVE","DR"),("STREET","ST")):s=re.sub(r"\b"+a+r"\b",b,s)
 return " ".join(re.sub(r"[^A-Z0-9 ]"," ",s).split())
def dparse(v):
 for fmt in ("%m/%d/%Y","%Y-%m-%d"):
  try:return datetime.datetime.strptime(str(v or "").strip(),fmt).date().isoformat()
  except ValueError:pass
 return None
def rows(path):
 with pathlib.Path(path).open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def build(seed,exports):
 base=rows(seed)
 if len(base)!=60 or len({p["county_pin"] for p in base})!=60:raise ValueError("Original 60 must be distinct")
 lookup=defaultdict(list);bypin={p["county_pin"]:p for p in base}
 for p in base:lookup[norm(p["address"])].append(p)
 events={};sources=[];issues=[]
 for file in exports:
  path=pathlib.Path(file);data=rows(path);digest=hashlib.sha256(path.read_bytes()).hexdigest();new=0;dates=[]
  for raw in data:
   pid=str(raw.get("Permit Number") or "").strip()
   if not pid:continue
   raw_address=str(raw.get("Address") or "");addr=norm(raw_address)
   pin=str(raw.get("Parcel Number") or raw.get("County Pin") or "").strip()
   if pin in bypin:
    matched=bypin[pin]
    if addr and addr!=norm(matched["address"]):
     issues.append({"permit":pid,"source":path.name,"reason":"PIN_ADDRESS_CONFLICT"});continue
   else:
    candidates=lookup.get(addr,[])
    if len(candidates)!=1:continue
    matched=candidates[0]
   issued=dparse(raw.get("Issue Date") or raw.get("Date Issued"))
   if issued:dates.append(issued)
   work=str(raw.get("Permit Type") or raw.get("Type") or "")
   desc=str(raw.get("Description") or "")
   trailing=raw_address.split(",",1)[1] if "," in raw_address else ""
   explicit=bool(re.search(r"\b(?:re[ -]?roof(?:ing)?|roof(?:ing)?|shingles?)\b",work+" "+desc+" "+trailing,re.I))
   kind="ROOF_CANDIDATE_PENDING_DOCUMENT_REVIEW" if explicit else ("EXTERIOR_MAINTENANCE_UNSPECIFIED" if "exterior maintenance" in work.lower() else "OTHER_PERMIT_TYPE")
   key=(matched["parcel_objectid"],pid)
   if key in events:continue
   events[key]={"parcel_objectid":matched["parcel_objectid"],"county_pin":matched["county_pin"],"permit_number":pid,
    "issued_date":issued,"permit_kind":kind,"source_report":path.name,
    "review_status":"SOURCE_EXPORT_MATCH_PENDING_HUMAN_REVIEW",
    "source_file_sha256":digest,
    "raw_row_sha256":hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()}
   new+=1
  sources.append({"file":path.name,"rows":len(data),"sha256":digest,"first_matching_issued_date":min(dates) if dates else None,
   "last_matching_issued_date":max(dates) if dates else None,"deduplicated_property_matches":new})
 records=list(events.values());group=defaultdict(list)
 for item in records:group[item["parcel_objectid"]].append(item)
 summaries=[{"parcel_objectid":id,"matches":len(matches),"roof_2025_candidates":sum(x["permit_kind"]=="ROOF_CANDIDATE_PENDING_DOCUMENT_REVIEW" and str(x.get("issued_date","")).startswith("2025-") for x in matches)} for id,matches in sorted(group.items())]
 return {"generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"scope":"Original 60, user-provided Eagan municipal exports",
  "total_source_rows":sum(s["rows"] for s in sources),"input_files":sources,"records":records,"properties":summaries,
  "matched_permit_events":len(records),"properties_with_matches":len(group),
  "properties_with_2025_roof_candidates":sum(x["roof_2025_candidates"]>0 for x in summaries),
  "municipal_export_ingested":True,"issuer_independently_rechecked":False,"permit_history_complete":False,
  "rejections":issues,"warning":"No match means no match in these report windows; original permit documentation required for roof decisions."}
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--seed",type=pathlib.Path,default=D/"kingswood_parcel_candidates.csv")
 p.add_argument("--export",nargs="+",required=True,type=pathlib.Path);p.add_argument("--out",type=pathlib.Path,default=D/"municipal_permit_export_audit.json")
 a=p.parse_args();out=build(a.seed,a.export);a.out.parent.mkdir(parents=True,exist_ok=True)
 a.out.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({k:out[k] for k in ("total_source_rows","matched_permit_events","properties_with_matches","properties_with_2025_roof_candidates")}))
