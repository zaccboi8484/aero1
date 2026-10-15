#!/usr/bin/env python3
"""Enrich real parcel candidates with image-service extent URLs. Python standard library.
No image is classified as roof damage; images stay hosted by Dakota County.
"""
import csv,json,pathlib,urllib.request,urllib.parse,time,datetime
R=pathlib.Path(__file__).resolve().parents[1]
source=R/"evidence/data/kingswood_parcel_candidates.csv"
dest=R/"evidence/data/imagery_manifest.json"
BASE="https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2/query"
SERVICES={
 "2026-spring-leaf-off":"2026AirPhotoLeafOff6Inch_Spring",
 "2025-spring-leaf-off":"2025AirPhotoLeafOff6Inch_Spring",
 "2025-fall-leaf-on":"2025AirPhotoLeafOn6Inch_Fall",
 "2023-spring-leaf-off":"2023AirPhotoLeafOff6Inch_Spring",
}
IMAGES="https://gisimg.co.dakota.mn.us/arcgis/rest/services/AerialPhotography/"
rows=list(csv.DictReader(source.open(encoding="utf-8")))
ids=[int(row["parcel_objectid"]) for row in rows if row["parcel_objectid"].isdigit()]
assert len(ids)==len(rows)
params={"f":"json","objectIds":",".join(map(str,ids)),"outFields":"OBJECTID","returnGeometry":"true","outSR":"4326"}
url=BASE+"?"+urllib.parse.urlencode(params)
req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-OfficialImagery-1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=40) as response:data=json.load(response)
if "error" in data:raise ValueError(data["error"])
centers={}
for feature in data.get("features",[]):
  attr=feature.get("attributes") or {}
  geom=feature.get("geometry") or {}
  paths=geom.get("rings") or geom.get("paths") or []
  points=[p for ring in paths for p in ring if isinstance(p,list) and len(p)>1]
  if not points and "x" in geom and "y" in geom:points=[[geom["x"],geom["y"]]]
  if points:
    xs=[float(p[0]) for p in points];ys=[float(p[1]) for p in points]
    x=(min(xs)+max(xs))/2;y=(min(ys)+max(ys))/2
    if -93.5<x<-92.5 and 44<y<45.5:centers[str(attr["OBJECTID"])]=(x,y)
results=[]
for row in rows:
  obj=row["parcel_objectid"];center=centers.get(obj)
  if not center:continue
  x,y=center
  # Approximate footprint: 110m east-west x 90m north-south, NOT legal parcel boundary.
  dx=.00070;dy=.00040
  bbox=[round(x-dx,7),round(y-dy,7),round(x+dx,7),round(y+dy,7)]
  layers={}
  for label,service in SERVICES.items():
    endpoint=IMAGES+service+"/ImageServer/exportImage"
    layers[label]=endpoint+"?"+urllib.parse.urlencode({"bbox":",".join(map(str,bbox)),"bboxSR":4326,"imageSR":4326,"size":"900,700","format":"jpg","f":"image"})
  results.append({"parcel_objectid":obj,"county_pin":row.get("county_pin"),"address":row["address"],
    "center_lon":round(x,7),"center_lat":round(y,7),"bbox_4326":bbox,
    "geometry_source":url,"image_layers":layers,"verification_status":"UNVERIFIED",
    "rights_notice":"Images served by Dakota County GIS; preserve county attribution and review usage terms.",
    "scope_note":"BBox is a viewing window centered on GIS polygon extent; not a roof or legal boundary."})
manifest={"generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "source":"Dakota County GIS ArcGIS ImageServer",
 "service_catalog":"https://gisimg.co.dakota.mn.us/arcgis/rest/services/AerialPhotography",
 "parcel_geometry_source":url,"count":len(results),"actual_images_downloaded":0,
 "imagery_urls_constructed_from_real_parcel_geometry":len(results),
 "remote_image_response_validated":False,
 "warning":"A generated ImageServer URL is NOT evidence that an image response loaded. No inspection findings, acquisition-specific timestamps, or permit matches.",
 "records":results}
dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
print("Created imagery request manifests for",len(results),"official parcel candidates")
