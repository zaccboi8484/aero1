#!/usr/bin/env python3
"""GateKeeper permit reconciliation. Python 3.11+, stdlib only.
Inputs: real exported City of Eagan permit CSV and official GIS parcel CSV.
Outputs: review queue + audit decisions; never invent findings.
Usage: python collector/match_permits.py --permits /path/to/eagan-export.csv
"""
import argparse,csv,datetime as dt,hashlib,json,pathlib,re,sys,urllib.parse

ROOT=pathlib.Path(__file__).resolve().parent.parent
DEFAULT_PARCELS=ROOT/"evidence/data/kingswood_parcel_candidates.csv"
OUT=ROOT/"evidence/data"
HEADERS={
 "address":["address","siteaddress","propertyaddress","permitaddress","location","streetaddress"],
 "number":["permitnumber","permitno","permitid","recordnumber","recordid","number"],
 "kind":["permittype","type","worktype","description","permitdescription"],
 "status":["status","permitstatus","recordstatus"],
 "issued":["issuedate","dateissued","issued","permitdate"],
 "source_url":["recordurl","permiturl","sourceurl","url"],
}
def canon(s):return re.sub(r"[^a-z0-9]", "",str(s or "").casefold())
def field(row,key):
  normalized={canon(k):v for k,v in row.items()}
  return next((normalized[k] for k in HEADERS[key] if k in normalized),"")
def address_key(raw):
  x=str(raw or "").upper().strip()
  x=re.sub(r"\b(EAGAN|MINNESOTA|MN|USA)\b"," ",x)
  x=re.sub(r"\b(ROAD|RD\.?|DRIVE|DR\.?|COURT|CT\.?|LANE|LN\.?)\b",lambda m:{"ROAD":"RD","RD":"RD","RD.":"RD","DRIVE":"DR","DR":"DR","DR.":"DR","COURT":"CT","CT":"CT","CT.":"CT","LANE":"LN","LN":"LN","LN.":"LN"}.get(m.group(0)," "),x)
  return re.sub(r"[^A-Z0-9]","",x)
def read_csv(path):
  with open(path,newline="",encoding="utf-8-sig") as f:
    return list(csv.DictReader(f))
def reconcile(parcels,permits,source_document):
  index={}
  for p in parcels:
    key=address_key(p.get("address"))
    if key:index.setdefault(key,[]).append(p)
  results=[];seen=set()
  for line,p in enumerate(permits,2):
    address=field(p,"address");key=address_key(address)
    candidates=index.get(key,[])
    num=field(p,"number");url=field(p,"source_url")
    reference=num or "csv-row-"+str(line)
    dedupe=hashlib.sha256((source_document+"|"+reference+"|"+address).encode()).hexdigest()
    if dedupe in seen:continue
    seen.add(dedupe)
    exact=len(candidates)==1 and bool(num) and bool(address)
    matched=candidates[0] if exact else None
    results.append({
      "source_document":source_document,"source_line":line,
      "source_record_id":num or None,"source_record_url":url or None,
      "source_address":address,"permit_type":field(p,"kind"),
      "permit_status":field(p,"status"),"issued_date_raw":field(p,"issued"),
      "county_pin":matched.get("county_pin") if matched else None,
      "parcel_objectid":matched.get("parcel_objectid") if matched else None,
      "match_status":"EXACT_ADDRESS_PENDING_REVIEW" if exact else ("AMBIGUOUS" if len(candidates)>1 else "UNMATCHED"),
      "verification_status":"UNVERIFIED",
      "classification":"UNKNOWN",
      "source_row_sha256":hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),
      "dedupe_key":dedupe,"inspection_claim":None
    })
  return results
def main():
  parser=argparse.ArgumentParser()
  parser.add_argument("--permits",type=pathlib.Path,required=True,help="Original public Eagan CSV export")
  parser.add_argument("--parcels",type=pathlib.Path,default=DEFAULT_PARCELS)
  parser.add_argument("--out",type=pathlib.Path,default=OUT/"permit_match_review.json")
  a=parser.parse_args()
  if not a.permits.is_file():parser.error("Permit source export must exist; no dummy records are generated")
  source_hash=hashlib.sha256(a.permits.read_bytes()).hexdigest()
  parcels=read_csv(a.parcels);permits=read_csv(a.permits)
  results=reconcile(parcels,permits,a.permits.name+"#sha256="+source_hash)
  manifest={"generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
   "original_permit_filename":a.permits.name,"original_permit_sha256":source_hash,
   "input_rows":len(permits),"output_rows":len(results),
   "parcel_candidates":len(parcels),
   "exact_address_pending_review":sum(x["match_status"]=="EXACT_ADDRESS_PENDING_REVIEW" for x in results),
   "reviewed_findings":0,"notes":"Exact address is only a candidate match. No findings promoted without coordinator review."}
  a.out.parent.mkdir(parents=True,exist_ok=True)
  a.out.write_text(json.dumps({"manifest":manifest,"records":results},indent=2)+"\n",encoding="utf-8")
  print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
