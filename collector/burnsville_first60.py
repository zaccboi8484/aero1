#!/usr/bin/env python3
"""Collect up to 60 real Burnsville parcel identities from MetroGIS.
No inferred permits, no invented properties. Uses county PIN + original source ID.
"""
import csv,datetime,json,pathlib,urllib.parse,urllib.request
SOURCE="https://arcgis.metc.state.mn.us/arcgis/rest/services/LPH/Administrative_Parcels/FeatureServer/0/query"
FIELDS="OBJECTID,COUNTY_PIN,STATE_PIN,ANUMBER,ST_NAME,ST_POS_TYP,CTU_NAME,CO_NAME,PLAT_NAME"
OUTPUT=pathlib.Path("evidence/data")
def fetch(offset):
 params={"f":"json","where":"UPPER(CTU_NAME) = 'BURNSVILLE' AND UPPER(CO_NAME) = 'DAKOTA'","outFields":FIELDS,"returnGeometry":"false","resultOffset":offset,"resultRecordCount":100,"orderByFields":"OBJECTID ASC"}
 url=SOURCE+"?"+urllib.parse.urlencode(params)
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-Burnsville-Parcels/1.0"}),timeout=50) as f:data=json.load(f)
 if data.get("error"):raise RuntimeError(data["error"])
 return data,url
def main():
 records=[];ids=set();offset=0;links=[]
 while len(records)<60:
  data,url=fetch(offset);links.append(url);items=data.get("features") or []
  if not items:break
  for feature in items:
   a=feature.get("attributes") or {};pin=str(a.get("COUNTY_PIN") or "").strip();oid=str(a.get("OBJECTID") or "")
   num=a.get("ANUMBER")
   if not pin or not oid or not num or pin in ids:continue
   if str(a.get("CTU_NAME") or "").casefold()!="burnsville":continue
   ids.add(pin)
   address=" ".join(str(x) for x in [num,a.get("ST_NAME") or "",a.get("ST_POS_TYP") or ""] if str(x).strip())+", Burnsville, MN"
   detail=SOURCE+"?"+urllib.parse.urlencode({"f":"json","where":"OBJECTID="+oid,"outFields":FIELDS,"returnGeometry":"false"})
   records.append({"territory_id":"burnsville-expansion","jurisdiction":"burnsville","county":"Dakota","county_pin":pin,"parcel_objectid":oid,"address":address,"plat_name":a.get("PLAT_NAME") or "","source_record_url":detail,"verification_status":"UNVERIFIED","permit_matches":0,"imagery_evidence":0})
   if len(records)>=60:break
  offset+=len(items)
  if len(items)<100:break
 OUTPUT.mkdir(parents=True,exist_ok=True)
 with (OUTPUT/"burnsville_first60_parcels.csv").open("w",newline="",encoding="utf-8") as f:
  writer=csv.DictWriter(f,fieldnames=list(records[0]) if records else ["territory_id","jurisdiction","county","county_pin","parcel_objectid","address","plat_name","source_record_url","verification_status","permit_matches","imagery_evidence"])
  writer.writeheader();writer.writerows(records)
 (OUTPUT/"burnsville_first60_manifest.json").write_text(json.dumps({"fetched_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"count":len(records),"requested":60,"status":"SOURCE_RECORD_CANDIDATES_NOT_PERMIT_VERIFIED","source_requests":links},indent=2)+"\n")
 print("Real Burnsville GIS parcel candidates:",len(records))
if __name__=="__main__":main()
