#!/usr/bin/env python3
"""Public Metropolitan Council residential-permit GIS search for the 60 Eagan parcels.
This source may cover construction permits rather than reroofing/repairs. A lack
of matches is not proof that a property has no permits. No scrape or bypass.
"""
import csv,json,pathlib,re,urllib.request,urllib.parse,hashlib,time
from datetime import datetime,timezone
DIR=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
BASE="https://arcgis.metc.state.mn.us/server/rest/services/EnterpriseLibrary/DTATResidentialPermits/FeatureServer/0/query"
NOW=datetime.now(timezone.utc).isoformat()
def normalize(value):
 t=re.sub(r"[^A-Z0-9 ]"," ",str(value or "").upper())
 for a,b in [(" ROAD "," RD "),(" LANE "," LN "),(" COURT "," CT "),(" DRIVE "," DR "),(" STREET "," ST "),(" AVENUE "," AV ")]:t=" "+t+" ";t=t.replace(a,b).strip()
 return " ".join(t.split())
def address_key(value):
 v=normalize(str(value or "").split(",")[0])
 v=re.sub(r"\b(EAGAN|MINNESOTA|MN|UNIT|APT)\b.*$","",v).strip()
 return v
with (DIR/"kingswood_parcel_candidates.csv").open(encoding="utf-8-sig",newline="") as f:parcels=list(csv.DictReader(f))
streetnames=sorted({x.get("street","") for x in parcels if x.get("street")})
roots=sorted({re.sub(r"\b(ROAD|LANE|COURT)\b","",x.upper()).strip() for x in streetnames})
index={}
for p in parcels:index.setdefault(address_key(p.get("address")),[]).append(p)
filters=["ADDRESS LIKE '%"+root.replace("'","''")+"%'" for root in roots if len(root)>=4]
where="UPPER(CTU_NAME) = 'EAGAN' AND ("+" OR ".join(filters)+")"
matches=[]
errors=[]
pages=0
unfiltered_count=0
complete=False
try:
 for offset in range(0,20000,2000):
  params={"f":"json","where":where,"outFields":"OBJECTID,CTU_NAME,CO_CODE,YEAR,RES_PERMIT_TYPE,HOUSING_TYPE_DESC,ADDRESS,NAME,UNITS,PERMIT_VALUE",
   "returnGeometry":"false","orderByFields":"OBJECTID ASC","resultOffset":offset,"resultRecordCount":2000}
  url=BASE+"?"+urllib.parse.urlencode(params)
  req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-OfficialEvidence/1.0","Accept":"application/json"})
  with urllib.request.urlopen(req,timeout=30) as r:response=json.load(r)
  if "error" in response:raise RuntimeError(str(response["error"])[:240])
  features=response.get("features",[])
  pages+=1
  unfiltered_count+=len(features)
  for feature in features:
   a=feature.get("attributes",{})
   targets=index.get(address_key(a.get("ADDRESS")),[])
   if len(targets)!=1:continue
   p=targets[0]
   obj=a.get("OBJECTID")
   item={"parcel_objectid":p["parcel_objectid"],"county_pin":p["county_pin"],"address":p["address"],
    "source_record_id":str(obj),"source_url":BASE+"?"+urllib.parse.urlencode({"f":"json","where":f"OBJECTID={obj}","outFields":"*","returnGeometry":"false"}),
    "permit_year":a.get("YEAR"),"permit_type_code":a.get("RES_PERMIT_TYPE"),
    "housing_type":a.get("HOUSING_TYPE_DESC"),"permit_value":a.get("PERMIT_VALUE"),
    "regional_record_address":a.get("ADDRESS"),"jurisdiction":a.get("CTU_NAME"),"match_status":"EXACT_ADDRESS_PENDING_REVIEW",
    "verification_status":"REGIONAL_AGGREGATE_NOT_MUNICIPAL_DOCUMENT","source_checked_utc":NOW}
   item["source_sha256"]=hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest()
   matches.append(item)
  if len(features)<2000:
   complete=True
   break
  time.sleep(.25)
except Exception as e:
 errors.append(str(e)[:300])
# Exact address matching is a candidate association, not final confirmed permit identity.
matched_ids={x["parcel_objectid"] for x in matches}
review=[{"parcel_objectid":p["parcel_objectid"],"county_pin":p["county_pin"],"address":p["address"],
  "status":"REGIONAL_CANDIDATE_MATCH_REVIEW_REQUIRED" if p["parcel_objectid"] in matched_ids else ("NO_REGIONAL_MATCH_IN_QUERY" if complete else "INCOMPLETE_SOURCE_QUERY"),
  "municipal_search":"NOT_COMPLETE_EAGAN_PORTAL_403",
  "match_count":sum(x["parcel_objectid"]==p["parcel_objectid"] for x in matches)} for p in parcels]
out={"checked_at_utc":NOW,"source_layer":BASE.rsplit("/query",1)[0],
  "source_method":"exact normalized address match after scoped authorized ArcGIS query",
  "scope":"Regional residential-permit dataset, not a comprehensive Eagan permit history; NOT a reroof registry",
  "query_completed":complete,"pages":pages,"regional_records_examined":unfiltered_count,
  "matches_pending_review":len(matches),"matched_properties":len(matched_ids),"total_properties":len(parcels),
  "errors":errors,"matches":matches,"properties":review}
(DIR/"regional_residential_permit_matches.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:out[k] for k in ("query_completed","pages","regional_records_examined","matched_properties","matches_pending_review","errors")},indent=2))
