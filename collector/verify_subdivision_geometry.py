#!/usr/bin/env python3
"""Validate GIS parcel-center points against CITY subdivision polygons.
Unlike a plat name comparison this performs an actual official GIS geometry query.
A center-in-plat result verifies the lookup point only, not a legal boundary survey.
"""
import csv,json,pathlib,urllib.parse,urllib.request,time,hashlib
from datetime import datetime,timezone
DATA=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
URL="https://gis.cityofeagan.com/arcgis/rest/services/EA_PropertyInformation/MapServer/9/query"
timestamp=datetime.now(timezone.utc).isoformat()
def read(name):
 try:return json.loads((DATA/name).read_text(encoding="utf-8"))
 except (OSError,ValueError):return {}
views={str(x.get("parcel_objectid")):x for x in read("imagery_manifest.json").get("records",[])}
with (DATA/"kingswood_parcel_candidates.csv").open(encoding="utf-8-sig",newline="") as f:parcels=list(csv.DictReader(f))
results=[]
for i,p in enumerate(parcels):
 oid=str(p.get("parcel_objectid") or "")
 entry={"parcel_objectid":oid,"county_pin":p.get("county_pin"),"address":p.get("address"),
    "query_timestamp_utc":timestamp,"verification_type":"PARCEL_CENTER_INTERSECTS_CITY_SUBDIVISION",
    "status":"NOT_CHECKED","source_url":URL}
 center=views.get(oid,{})
 lat=center.get("center_lat");lon=center.get("center_lon")
 try:
  if not isinstance(lat,(float,int)) or not isinstance(lon,(float,int)):raise ValueError("No official GIS-derived parcel center")
  params={"f":"json","geometry":json.dumps({"x":lon,"y":lat,"spatialReference":{"wkid":4326}}),
          "geometryType":"esriGeometryPoint","inSR":4326,"spatialRel":"esriSpatialRelIntersects",
          "where":"1=1","outFields":"OBJECTID,PLATNAME,PLATID","returnGeometry":"false"}
  url=URL+"?"+urllib.parse.urlencode(params)
  entry["source_url"]=url
  req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-EvidenceCollector/1.0","Accept":"application/json"})
  with urllib.request.urlopen(req,timeout=18) as resp:body=json.load(resp)
  if "error" in body:raise RuntimeError(str(body["error"])[:160])
  features=body.get("features",[])
  names=[f.get("attributes",{}).get("PLATNAME") for f in features if f.get("attributes",{}).get("PLATNAME")]
  matches=[n for n in names if "KINGS WOOD" in n.upper()]
  entry["matched_plats"]=matches
  entry["all_polygon_matches"]=names[:15]
  entry["status"]="OFFICIAL_CENTER_IN_KINGS_WOOD_PLAT" if matches else ("CENTER_IN_OTHER_PLAT" if names else "CENTER_NOT_IN_RETURNED_PLAT")
 except Exception as e:
  entry["status"]="SOURCE_ERROR"
  entry["error"]=str(e)[:220]
 entry["sha256"]=hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest()
 results.append(entry)
 if i< len(parcels)-1:time.sleep(0.10)
stats={status:sum(x["status"]==status for x in results) for status in sorted(set(x["status"] for x in results))}
out={"generated_at_utc":timestamp,"source":URL,"counts":stats,"total":len(results),"records":results,
     "disclaimer":"Confirmed here means GIS parcel-center point intersected the city plat polygon, not a survey or roof-condition finding."}
(DATA/"subdivision_geometry_checks.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"total":len(results),"counts":stats}))
