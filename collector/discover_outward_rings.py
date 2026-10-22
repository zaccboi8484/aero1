#!/usr/bin/env python3
"""AeroLeadAI real geographic outward parcel crawler. No fabricated lead records.
The first 60 remain Territory 001. New candidate rings are separate until
source, identity, and territory validation succeeds.
"""
import csv,datetime as dt,hashlib,json,math,pathlib,time,urllib.parse,urllib.request
BASE="https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2/query"
D=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
ATTR="OBJECTID,COUNTY_PIN,STATE_PIN,ANUMBER,ST_NAME,ST_POS_TYP,CTU_NAME,PLAT_NAME,ZIP,YEAR_BUILT"
def load(name):
 try:return json.loads((D/name).read_text(encoding="utf-8"))
 except (OSError,ValueError):return {}
def hav(lat1,lon1,lat2,lon2):
 r=6371008.8;p1,p2=math.radians(lat1),math.radians(lat2)
 dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1)
 a=math.sin(dphi/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
 return 2*r*math.asin(min(1,math.sqrt(a)))
def get(params):
 u=BASE+"?"+urllib.parse.urlencode(params)
 req=urllib.request.Request(u,headers={"User-Agent":"AeroLeadAI-OfficialParcelRings/1.0","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=35) as f:data=json.load(f)
 if "error" in data:raise RuntimeError(str(data["error"])[:300])
 return data,u
def collect(max_m=2100,ring_m=500,max_pages=15,offline=False):
 with (D/"kingswood_parcel_candidates.csv").open(newline="",encoding="utf-8-sig") as f:seed=list(csv.DictReader(f))
 imagery=load("imagery_manifest.json")
 points=[(float(x["center_lat"]),float(x["center_lon"])) for x in imagery.get("records",[]) if isinstance(x.get("center_lat"),(float,int)) and isinstance(x.get("center_lon"),(float,int))]
 if len(points)!=len(seed):raise RuntimeError("Stop ring discovery: first 60 have incomplete official GIS centroids")
 center_lat=sum(x[0] for x in points)/len(points);center_lon=sum(x[1] for x in points)/len(points)
 max_seed=max(hav(center_lat,center_lon,lat,lon) for lat,lon in points)
 inner=max_seed+25
 seen_pins={str(p["county_pin"]) for p in seed}
 seen_oids={str(p["parcel_objectid"]) for p in seed}
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 result={"generated_at_utc":now,"source":BASE,"seed_count":len(seed),"seed_center_lat":center_lat,"seed_center_lon":center_lon,
  "seed_radius_m":round(max_seed,1),"distance_from_seed_boundary_approximation":True,
  "discovery_rule":"Source-supported center-distance bands; does not claim a survey-quality legal ring boundary",
  "ring_width_m":ring_m,"search_radius_m":max_m,"ring_candidates":[],"candidate_count":0,"source_query_completed":False,"pages":0,"errors":[]}
 if offline:
  result["errors"].append("Not queried: explicit offline mode");return result
 # Server uses actual ArcGIS geodesic distance filtering of official parcel polygons.
 seen={}
 for offset in range(0,max_pages*500,500):
  params={"f":"json","where":"UPPER(CTU_NAME) = 'EAGAN'","geometry":json.dumps({"x":center_lon,"y":center_lat,"spatialReference":{"wkid":4326}}),
  "geometryType":"esriGeometryPoint","inSR":"4326","spatialRel":"esriSpatialRelIntersects","distance":int(max_m),
  "units":"esriSRUnit_Meter","outFields":ATTR,"outSR":"4326","returnGeometry":"true",
  "resultOffset":offset,"resultRecordCount":500,"orderByFields":"OBJECTID ASC"}
  try:
   data,source_url=get(params);result["pages"]+=1
   feats=data.get("features",[])
   for row in feats:
    a=row.get("attributes") or {};oid=str(a.get("OBJECTID") or "");pin=str(a.get("COUNTY_PIN") or "")
    if not oid or not pin or oid in seen_oids or pin in seen_pins or pin in seen:continue
    geom=row.get("geometry") or {}
    rings=geom.get("rings") or []
    coordinates=[p for ring in rings for p in ring if isinstance(p,list) and len(p)>=2]
    if not coordinates:continue
    # Center of polygon bounding envelope; approximate only and never used to assert legal parcel boundaries.
    lat=(min(p[1] for p in coordinates)+max(p[1] for p in coordinates))/2
    lon=(min(p[0] for p in coordinates)+max(p[0] for p in coordinates))/2
    dist=hav(center_lat,center_lon,lat,lon)
    if dist<inner or dist>max_m:continue
    ring=int((dist-inner)//ring_m)+1
    address=" ".join(str(a.get(k) or "").strip() for k in ("ANUMBER","ST_NAME","ST_POS_TYP")).strip()
    if not address or not str(a.get("ANUMBER") or "").strip():continue
    match={"parcel_objectid":oid,"county_pin":pin,"address":address+", Eagan, MN",
     "plat_name":a.get("PLAT_NAME"),"year_built":a.get("YEAR_BUILT"),"zip":a.get("ZIP"),
     "center_lat":round(lat,7),"center_lon":round(lon,7),"distance_from_seed_center_m":round(dist,1),
     "ring":ring,"bbox_4326":[round(min(q[0] for q in coordinates),7),round(min(q[1] for q in coordinates),7),round(max(q[0] for q in coordinates),7),round(max(q[1] for q in coordinates),7)],"verification_status":"OFFICIAL_GIS_SOURCE_CANDIDATE","condition_status":"NOT_INSPECTED",
     "source_record_url":BASE+"?"+urllib.parse.urlencode({"f":"json","where":"OBJECTID="+oid,"outFields":ATTR,"returnGeometry":"false"})}
    match["evidence_sha256"]=hashlib.sha256(json.dumps(match,sort_keys=True).encode()).hexdigest()
    seen[pin]=match
   if len(feats)<500:
    result["source_query_completed"]=True;break
   time.sleep(.15)
  except Exception as e:
   result["errors"].append(str(e)[:280]);break
 for item in sorted(seen.values(),key=lambda r:(r["ring"],r["distance_from_seed_center_m"],r["county_pin"])):result["ring_candidates"].append(item)
 result["candidate_count"]=len(seen)
 result["counts_by_ring"]={str(r):sum(x["ring"]==r for x in seen.values()) for r in sorted({x["ring"] for x in seen.values()})}
 if not result["source_query_completed"] and result["pages"]>=max_pages:result["errors"].append("Page budget reached; incomplete query")
 return result
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--no-network",action="store_true");p.add_argument("--radius",type=int,default=0);args=p.parse_args()
 prev=load("outward_ring_candidates.json")
 previous_radius=int(prev.get("search_radius_m") or max((x.get("distance_from_seed_center_m") or 0 for x in prev.get("ring_candidates",[])),default=1200))
 selected_radius=min(max(args.radius or (previous_radius+500),700),5000)
 out=collect(max_m=selected_radius,offline=args.no_network)
 D.mkdir(parents=True,exist_ok=True)
 if not out["source_query_completed"] or out["errors"]:
  (D/"outward_ring_discovery_failure.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
  raise SystemExit("Official parcel discovery incomplete; preserved previous verified ring registry")
 (D/"outward_ring_candidates.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({k:out.get(k) for k in ("seed_count","candidate_count","source_query_completed","counts_by_ring","pages","errors")},indent=2))
if __name__=="__main__":main()
