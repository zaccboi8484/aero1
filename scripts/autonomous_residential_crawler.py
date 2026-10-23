#!/usr/bin/env python3
"""Source-backed incremental residential parcel discovery.
Checkpoint persists in Git. No invented owners, permits, roof condition or values.
"""
import json, os, time, urllib.parse, urllib.request, pathlib, datetime, math
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence"/"data"/"autonomous_residential_discovery.json"
URL="https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2/query"
CENTER=(44.816482341666664,-93.17033227666667)
WIDTH=500
MAX_RADIUS=40000
FIELDS="OBJECTID,COUNTY_PIN,CTU_NAME,ANUMBER,ST_NAME,ST_POS_TYP,ZIP,YEAR_BUILT,LAND_USE,USE_CODE,PROPERTY_TYPE"
def get(params):
    uri=URL+"?"+urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(uri,headers={"User-Agent":"AeroLeadAI-public-data-research/1.0"}),timeout=35) as r:
        value=json.load(r)
    if value.get("error"): raise RuntimeError(str(value["error"]))
    return value
def km(lat,lon):
    a,b=map(math.radians,CENTER);c,d=map(math.radians,(lat,lon))
    return 12742.0176*math.asin(min(1,math.sqrt(math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2)))
def run():
    current=json.loads(OUT.read_text()) if OUT.exists() else {}
    parcels={p["county_pin"]:p for p in current.get("records",[]) if p.get("county_pin")}
    # Advance only after a successful batch. Retry same distance after failure.
    ring=int(current.get("next_ring",1))
    if ring*WIDTH>MAX_RADIUS: ring=1
    distance=ring*WIDTH
    # Query official source by bounding box, then enforce ring membership using GIS centroid.
    lat_radius=distance/111320
    lon_radius=distance/(111320*max(.2,math.cos(math.radians(CENTER[0]))))
    geometry=f"{CENTER[1]-lon_radius},{CENTER[0]-lat_radius},{CENTER[1]+lon_radius},{CENTER[0]+lat_radius}"
    where="UPPER(CTU_NAME) = 'EAGAN'"
    ids=get({"f":"json","where":where,"geometry":geometry,"geometryType":"esriGeometryEnvelope","inSR":"4326","spatialRel":"esriSpatialRelIntersects","returnIdsOnly":"true"})
    object_ids=sorted(set(ids.get("objectIds") or []))
    accepted=0
    for start in range(0,len(object_ids),100):
        batch=get({"f":"json","objectIds":",".join(map(str,object_ids[start:start+100])),"outFields":"*","returnGeometry":"true","outSR":"4326"})
        for f in batch.get("features",[]):
            a=f.get("attributes") or {};geom=f.get("geometry") or {}
            # ArcGIS parcel polygon: derive approximate center from vertices, never pretend it is surveyed.
            pts=[]
            for ring_coords in geom.get("rings",[]):
                pts.extend((x,y) for x,y in ring_coords if isinstance(x,(int,float)) and isinstance(y,(int,float)))
            if not pts: continue
            lon=(min(x for x,y in pts)+max(x for x,y in pts))/2
            lat=(min(y for x,y in pts)+max(y for x,y in pts))/2
            d=km(lat,lon)*1000
            if not (distance-WIDTH <= d < distance):continue
            pin=str(a.get("COUNTY_PIN") or "").strip()
            if not pin: continue
            # Residential type is unverified unless source explicitly supports it; skip confirmed non-residential.
            classification=" ".join(str(a.get(k) or "") for k in ("LAND_USE","PROPERTY_TYPE","USE_CODE")).upper()
            if any(x in classification for x in ("COMMERCIAL","INDUSTRIAL","SCHOOL","WAREHOUSE","APARTMENT","MULTIFAMILY")):continue
            road=" ".join(str(a.get(k) or "").strip() for k in ("ANUMBER","ST_NAME","ST_POS_TYP")).strip()
            prior=parcels.get(pin,{})
            parcels[pin]={**prior,"county_pin":pin,"parcel_objectid":str(a.get("OBJECTID") or ""),"address":road or prior.get("address"),
                "center_lat":round(lat,7),"center_lon":round(lon,7),"ring":ring,
                "year_built":a.get("YEAR_BUILT"),"land_use":classification or None,
                "single_family_verified":("SINGLE FAMILY" in classification or "SINGLE-FAMILY" in classification),
                "source":URL,"last_seen_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "roof_condition":"NOT_VERIFIED","permit_history":"NOT_VERIFIED",
                "recorded_owner":"NOT_VERIFIED","valuation":"NOT_VERIFIED"}
            accepted+=1
        time.sleep(.2)
    next_ring=ring+1 if distance<MAX_RADIUS else 1
    OUT.parent.mkdir(parents=True,exist_ok=True)
    doc={"format":"AERO_AUTONOMOUS_RESIDENTIAL_V1","center_lat":CENTER[0],"center_lon":CENTER[1],
         "ring_width_m":WIDTH,"next_ring":next_ring,"last_completed_ring":ring,
         "last_completed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "last_ring_candidates":accepted,"records":sorted(parcels.values(),key=lambda x:x["county_pin"])}
    temp=OUT.with_suffix(".tmp");temp.write_text(json.dumps(doc,indent=2)+"\n");temp.replace(OUT)
    print("Completed ring",ring,"records",len(parcels),"candidates in ring",accepted)
if __name__=="__main__":run()
