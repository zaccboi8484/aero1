#!/usr/bin/env python3
"""AeroLeadAI address-point crosscheck. Official GIS is not USPS deliverability."""
import argparse,csv,datetime as dt,json,os,pathlib,re,time,urllib.parse,urllib.request
BASE="https://arcgis.metc.state.mn.us/server/rest/services/GISLibrary/VWAddressPointsCommons/FeatureServer/0/query"
def norm(v):
 s=re.sub(r"[^A-Z0-9 ]"," ",str(v or "").upper())
 for name,short in [("ROAD","RD"),("LANE","LN"),("COURT","CT"),("DRIVE","DR"),("STREET","ST"),("AVENUE","AVE")]:s=re.sub(r"\b"+name+r"\b",short,s)
 return " ".join(s.split())
def request(url,headers=None):
 req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-SourceAudit/2.0","Accept":"application/json",**(headers or {})})
 with urllib.request.urlopen(req,timeout=25) as f:data=json.load(f)
 if isinstance(data,dict) and "error" in data:raise RuntimeError(str(data["error"]))
 return data
def main():
 pa=argparse.ArgumentParser();pa.add_argument("--data-dir",default="evidence/data");pa.add_argument("--no-network",action="store_true");pa.add_argument("--usps",action="store_true");a=pa.parse_args()
 d=pathlib.Path(a.data_dir);d.mkdir(parents=True,exist_ok=True)
 with (d/"kingswood_parcel_candidates.csv").open(newline="",encoding="utf-8-sig") as f:parcels=list(csv.DictReader(f))
 streets=sorted(set(re.sub(r"\b(ROAD|LANE|COURT)\b","",p.get("street","").upper()).strip() for p in parcels if p.get("street")))
 where="UPPER(CTU_NAME)='EAGAN' AND ("+" OR ".join("UPPER(ST_NAME) LIKE '%"+v.replace("'","''")+"%'" for v in streets if len(v)>=3)+")"
 matches=[];error=None
 if not a.no_network:
  try:
   for offset in range(0,10000,2000):
    q={"f":"json","where":where,"outFields":"OBJECTID,ADD_ID,ANUMBER,ST_NAME,ST_POS_TYP,CTU_NAME,STATE_PIN,ZIP,ZIP4,MAILABLE","returnGeometry":"false","resultOffset":offset,"resultRecordCount":2000}
    uri=BASE+"?"+urllib.parse.urlencode(q);items=request(uri).get("features",[])
    matches.extend([{**x["attributes"],"_source_url":uri} for x in items])
    if len(items)<2000:break
    time.sleep(.1)
  except Exception as ex:error=str(ex)[:200]
 else:error="Offline mode: no address lookup attempted"
 idx={}
 for x in matches:idx.setdefault(norm(str(x.get("ANUMBER"))+" "+str(x.get("ST_NAME"))+" "+str(x.get("ST_POS_TYP"))),[]).append(x)
 records=[]
 for p in parcels:
  key=norm(p.get("address","").split(",")[0]);found=idx.get(key,[])
  status="STATE_GIS_ADDRESS_MATCH" if len(found)==1 else "AMBIGUOUS_GIS_ADDRESS" if len(found)>1 else "GIS_ADDRESS_NOT_FOUND"
  if error:status="GIS_SOURCE_UNAVAILABLE"
  first=found[0] if len(found)==1 else {}
  records.append({"parcel_objectid":p.get("parcel_objectid"),"county_pin":p.get("county_pin"),"address":p.get("address"),"normalized":key,"status":status,"address_point_id":first.get("ADD_ID"),"zip":first.get("ZIP"),"zip4":first.get("ZIP4"),"mailable_gis_flag":first.get("MAILABLE"),"source_url":first.get("_source_url",BASE),"usps_status":"NOT_CONNECTED_MISSING_OAUTH"})
 cid=os.environ.get("USPS_CLIENT_ID");secret=os.environ.get("USPS_CLIENT_SECRET")
 if a.usps and not a.no_network and cid and secret:
  try:
   payload=json.dumps({"client_id":cid,"client_secret":secret,"grant_type":"client_credentials"}).encode()
   req=urllib.request.Request("https://apis.usps.com/oauth2/v3/token",method="POST",data=payload,headers={"Content-Type":"application/json","Accept":"application/json"})
   with urllib.request.urlopen(req,timeout=20) as f:token=json.load(f).get("access_token")
   if not token:raise RuntimeError("No USPS token")
   for p in records:
    try:
     address=p["address"].split(",")[0];uri="https://apis.usps.com/addresses/v3/address?"+urllib.parse.urlencode({"streetAddress":address,"city":"Eagan","state":"MN"})
     response=request(uri,{"Authorization":"Bearer "+token})
     standardized=response.get("address",{})
     p["usps_status"]="USPS_STANDARDIZED_PENDING_REVIEW" if standardized else "USPS_NO_STANDARDIZED_RESULT"
     if standardized:p["usps_standardized"]=standardized
    except Exception as ex:p["usps_status"]="USPS_API_ERROR";p["usps_error"]=str(ex)[:100]
    time.sleep(.2)
  except Exception as ex:error=(error or "")+" USPS auth unavailable: "+str(ex)[:120]
 elif a.usps and not(cid and secret):error=(error or "")+" USPS API not connected"
 out={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"address_source":BASE,"usps_docs":"https://developers.usps.com/addressesv3","total":len(records),"gis_address_matched":sum(x["status"]=="STATE_GIS_ADDRESS_MATCH" for x in records),"usps_standardized":sum(x["usps_status"]=="USPS_STANDARDIZED_PENDING_REVIEW" for x in records),"source_errors":[error] if error else [],"records":records,"gatekeeper_note":"GIS address point != USPS mail delivery certification. USPS credentials remain server-only."}
 (d/"mn_address_validation.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"total":len(records),"gis_address_matched":out["gis_address_matched"],"usps_standardized":out["usps_standardized"],"source_errors":out["source_errors"]}))
if __name__=="__main__":main()
