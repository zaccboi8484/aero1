#!/usr/bin/env python3
"""Fetch up to 60 real ArcGIS parcel candidates. No synthetic or private records."""
import csv, json, os, pathlib, time, urllib.parse, urllib.request
from datetime import datetime, timezone
BASE="https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2/query"
FIELDS=["OBJECTID","COUNTY_PIN","STATE_PIN","ANUMBER","ST_NAME","ST_POS_TYP","CTU_NAME","PLAT_NAME","ZIP","YEAR_BUILT"]
WHERE="UPPER(CTU_NAME) = 'EAGAN' AND UPPER(ST_NAME) LIKE '%KINGS WOOD%'"
ROOT=pathlib.Path(__file__).resolve().parent.parent/"evidence"/"data"
ROOT.mkdir(parents=True,exist_ok=True)
def query(params):
    url=BASE+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-EvidenceCollector/1.0 (public parcels; contact repository maintainer)","Accept":"application/json"})
    for trial in range(3):
        try:
            with urllib.request.urlopen(req,timeout=35) as f: out=json.load(f)
            if "error" in out: raise RuntimeError(str(out["error"]))
            return out,url
        except Exception:
            if trial==2:raise
            time.sleep(2*(trial+1))
    raise AssertionError
rows=[];offset=0;seen=set();queries=[]
while len(rows)<60:
    data,url=query({"f":"json","where":WHERE,"outFields":",".join(FIELDS),"returnGeometry":"false","orderByFields":"OBJECTID ASC","resultOffset":offset,"resultRecordCount":100})
    queries.append(url)
    features=data.get("features",[])
    if not features:break
    for feature in features:
        attrs=feature.get("attributes") or {}
        if not attrs.get("OBJECTID") or str(attrs.get("CTU_NAME","")).upper()!="EAGAN":continue
        if "KINGS WOOD" not in str(attrs.get("ST_NAME","")).upper():continue
        pin=attrs.get("COUNTY_PIN")
        oid=str(attrs["OBJECTID"])
        if oid in seen:continue
        seen.add(oid)
        number=attrs.get("ANUMBER")
        if not number:continue
        street=" ".join(str(attrs.get(k) or "") for k in ["ST_NAME","ST_POS_TYP"]).strip()
        rows.append({"parcel_objectid":oid,"county_pin":pin or "","state_pin":attrs.get("STATE_PIN") or "","address":str(number)+" "+street+", Eagan, MN","street":street,"plat_name":attrs.get("PLAT_NAME") or "","year_built":attrs.get("YEAR_BUILT") or "","source":"metc_dakota_parcels_2025","source_record_url":BASE+"?"+urllib.parse.urlencode({"f":"json","where":"OBJECTID="+oid,"outFields":",".join(FIELDS),"returnGeometry":"false"}),"verification_status":"UNVERIFIED","match_scope":"Eagan Kings Wood street candidate; subdivision boundary NOT validated"})
        if len(rows)>=60:break
    offset+=len(features)
    if len(features)<100:break
    time.sleep(.7)
stamp=datetime.now(timezone.utc).isoformat()
cols=["parcel_objectid","county_pin","state_pin","address","street","plat_name","year_built","source","source_record_url","verification_status","match_scope"]
path=ROOT/"kingswood_parcel_candidates.csv"
with path.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
(ROOT/"collection_manifest.json").write_text(json.dumps({"collected_at_utc":stamp,"source_layer":BASE,"filter":WHERE,"count":len(rows),"requested_max":60,"status":"SOURCE_RECORD_CANDIDATES_NOT_SUBDIVISION_VERIFIED","permit_matches":0,"inspection_findings":0,"imagery_attachments":0,"source_queries":queries,"note":"Only ArcGIS-returned Eagan Kings Wood street candidates, no inferred conditions."},indent=2)+"\n")
print("Collected",len(rows),"genuine GIS records; wrote",path)
