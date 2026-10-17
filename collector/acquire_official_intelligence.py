#!/usr/bin/env python3
"""AeroLeadAI live enrichment: municipal assessments, current NOAA alerts, GateKeeper audit.
This DOES issue official public source requests. No guessed matches, damage or scores.
Stdlib only. Failed sources produce auditable failures and retain prior confirmed records.
"""
import csv,hashlib,json,pathlib,re,time,urllib.parse,urllib.request
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
CITY="https://gis.cityofeagan.com/arcgis/rest/services/EA_PropertyInformation/MapServer/19/query"
NOAA="https://api.weather.gov/alerts/active?point=44.819,-93.167"
STAMP=datetime.now(timezone.utc).isoformat()
def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-OfficialEvidence/1.0 (public property intelligence; github.com/zaccboi8484/aero1)","Accept":"application/geo+json,application/json"})
 with urllib.request.urlopen(req,timeout=35) as r:return json.load(r)
def log(stage,state,source,detail="",count=None):
 event={"timestamp_utc":STAMP,"stage":stage,"state":state,"source":source,"detail":str(detail)[:240]}
 if count is not None:event["count"]=count
 audit.append(event)
def normalize(x):
 s=re.sub(r"[^A-Z0-9 ]"," ",str(x or "").upper())
 s=re.sub(r"\b(ROAD|RD)\b","RD",s);s=re.sub(r"\b(COURT|CT)\b","CT",s)
 s=re.sub(r"\b(DRIVE|DR)\b","DR",s);s=re.sub(r"\b(LANE|LN)\b","LN",s)
 s=re.sub(r"\b(EAGAN|MN|MINNESOTA)\b","",s)
 return " ".join(s.split())
def persist(name,data):
 (ROOT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
audit=[]
with (ROOT/"kingswood_parcel_candidates.csv").open(newline="",encoding="utf-8-sig") as f:parcels=list(csv.DictReader(f))
old={}
try:
 for record in json.loads((ROOT/"live_property_enrichment.json").read_text()).get("records",[]):
  if record.get("valuation",{}).get("gatekeeper")=="SOURCE_RECORDED":old[str(record.get("parcel_objectid"))]=record
except (FileNotFoundError,ValueError):pass
index={}
for p in parcels:index.setdefault(normalize(p["address"]),[]).append(p)
valuation={}
try:
 # Query the official city parcel GIS by house number and property address. No owner/taxpayer fields.
 # Batch query uses distinct number ranges; city has a public 1000-record service page limit.
 addresses=sorted(set(normalize(p["address"]).split(" ")[0] for p in parcels if p.get("address")))
 for group_start in range(0,len(addresses),35):
  group=addresses[group_start:group_start+35]
  where=" OR ".join("PHOUSE='"+v+"'" for v in group if v.isdigit())
  if not where:continue
  offset=0
  for page in range(10):
   query={"f":"json","where":"PCITY = 'EAGAN' AND ("+where+")","outFields":"OBJECTID_1,OLDPIN,TAXPIN,PHOUSE,PSTREET,PCITY,YRBUILT,LANDVAL,BLDGVAL,TOTALVAL","returnGeometry":"false","resultOffset":offset,"resultRecordCount":500}
   url=CITY+"?"+urllib.parse.urlencode(query)
   data=fetch(url)
   if data.get("error"):raise RuntimeError(str(data["error"])[:240])
   features=data.get("features",[])
   for x in features:
    a=x.get("attributes",{})
    key=normalize(str(a.get("PHOUSE") or "")+" "+str(a.get("PSTREET") or ""))
    targets=index.get(key,[])
    if len(targets)!=1:continue
    parcel=targets[0]
    # The city's own TAXPIN or OLDPIN must agree with the official county PIN.
    pin=str(parcel.get("county_pin") or "").lstrip("0")
    citypins=[str(a.get(k) or "").replace("-","").lstrip("0") for k in ("TAXPIN","OLDPIN")]
    if pin not in citypins:continue
    price=a.get("TOTALVAL")
    if not isinstance(price,(int,float)) or price<=0:continue
    oid=str(parcel["parcel_objectid"])
    valuation[oid]={"parcel_objectid":oid,"county_pin":parcel["county_pin"],"address":parcel["address"],
      "valuation":{"amount_usd":price,"land_value_usd":a.get("LANDVAL"),"building_value_usd":a.get("BLDGVAL"),
       "year_built":a.get("YRBUILT"),"assessment_year":"NOT_PUBLISHED_IN_LAYER",
       "source_url":url,"source_objectid":a.get("OBJECTID_1"),"acquired_at_utc":STAMP,
       "gatekeeper":"SOURCE_RECORDED","review_status":"UNREVIEWED"},
      "mindex":{"score":None,"status":"NOT_SCORED","reason":"No independently reviewed property-condition and storm evidence"}}
   offset+=len(features)
   if len(features)<500:break
  time.sleep(.3)
 log("valuation","SOURCE_RETURNED",CITY,count=len(valuation))
except Exception as e:log("valuation","SOURCE_ERROR",CITY,str(e))
for p in parcels:
 oid=str(p.get("parcel_objectid"))
 if oid not in valuation:
  valuation[oid]=old.get(oid,{"parcel_objectid":oid,"county_pin":p.get("county_pin"),"address":p.get("address"),
   "valuation":{"amount_usd":None,"gatekeeper":"NOT_RETRIEVED","reason":"No unambiguous public CITY parcel match and county PIN confirmation"},
   "mindex":{"score":None,"status":"NOT_SCORED","reason":"Reviewed evidence missing"}})
alerts=[]
try:
 data=fetch(NOAA)
 for feature in data.get("features",[]):
  a=feature.get("properties",{})
  if not a.get("id"):continue
  alerts.append({"event":a.get("event"),"identifier":a.get("id"),"sent":a.get("sent"),"effective":a.get("effective"),"expires":a.get("expires"),"severity":a.get("severity"),"source_url":a.get("@id") or a.get("id")})
 log("noaa_active_alerts","SOURCE_RETURNED",NOAA,count=len(alerts))
except Exception as e:log("noaa_active_alerts","SOURCE_ERROR",NOAA,str(e))
# NOAA alerts are geographic-area advisories, not lot-specific historical storm occurrences.
# Never translate them into claims of storm exposure, hail damage or an Mindex score.
records=[valuation[str(p["parcel_objectid"])] for p in parcels if str(p.get("parcel_objectid")) in valuation]
persist("live_property_enrichment.json",{"generated_utc":STAMP,"source_catalog":[CITY,NOAA],
 "records":records,"active_area_alerts":alerts,"disclaimer":"Current regional NOAA alerts, NOT verified historical property storm exposure. Eagan assessment year not available from returned fields.",
 "counts":{"parcels":len(records),"assessments_sourced":sum(r["valuation"].get("gatekeeper")=="SOURCE_RECORDED" for r in records),"reviewed_mindex":0,"noaa_active_alerts":len(alerts)}})
for entry in audit:
 entry["digest_sha256"]=hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest()
persist("live_acquisition_audit.json",{"run_at_utc":STAMP,"checks":audit,"no_assumed_success":True})
print(json.dumps({"assessment_sourced":sum(r["valuation"].get("gatekeeper")=="SOURCE_RECORDED" for r in records),"alerts":len(alerts),"audit":audit},indent=2))
