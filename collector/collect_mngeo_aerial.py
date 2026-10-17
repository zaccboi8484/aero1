#!/usr/bin/env python3
"""AeroLeadAI MnGeo official WMS imagery probe. Valid source images are NOT proof of defects."""
import argparse,datetime as dt,hashlib,json,pathlib,time,urllib.parse,urllib.request
BASE="https://imageserver.gisdata.mn.gov/cgi-bin/wmsll"
LAYERS=(("met25","2025 Twin Cities metro 1-foot"),("dak23","2023 Dakota County 6-inch"),("fsa2025","2025 FSA 0.6-meter"))
def url(bbox,layer):
 if layer not in dict(LAYERS):raise ValueError("Disallowed imagery layer")
 p=dict(SERVICE="WMS",VERSION="1.1.1",REQUEST="GetMap",LAYERS=layer,STYLES="",SRS="EPSG:4326",BBOX=",".join(map(str,bbox)),WIDTH="900",HEIGHT="700",FORMAT="image/jpeg")
 return BASE+"?"+urllib.parse.urlencode(p)
def verify(link):
 req=urllib.request.Request(link,headers={"User-Agent":"AeroLeadAI-SourceAudit/2.0","Accept":"image/jpeg"})
 with urllib.request.urlopen(req,timeout=13) as response:
  payload=response.read(2500001)
  if not(150<len(payload)<=2500000 and payload[:3]==b"\xff\xd8\xff" and payload[-2:]==b"\xff\xd9"):raise ValueError("Source response not valid JPEG")
  return {"bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest(),"content_type":response.headers.get("Content-Type","")}
def run(d,offline=False,limit=60):
 manifest=json.loads((d/"imagery_manifest.json").read_text(encoding="utf-8"))
 result=[];failures=0
 for x in manifest.get("records",[])[:limit]:
  r={"parcel_objectid":str(x.get("parcel_objectid")),"county_pin":x.get("county_pin"),"status":"NOT_CHECKED","layers":{},"preferred_layer":None,"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat()}
  bbox=x.get("bbox_4326")
  if not isinstance(bbox,list) or len(bbox)!=4:
   r["status"]="MISSING_BBOX";result.append(r);continue
  for layer,label in LAYERS:
   link=url(bbox,layer);detail={"layer":layer,"description":label,"source_url":link}
   if offline:detail["status"]="NOT_PROBED_OFFLINE"
   elif failures>=3:detail["status"]="SOURCE_CIRCUIT_OPEN"
   else:
    try:
     detail.update(verify(link));detail["status"]="REMOTE_IMAGE_VERIFIED";r["preferred_layer"]=layer;failures=0
    except Exception as exc:
     failures+=1;detail.update(status="SOURCE_ERROR",error=str(exc)[:200])
   r["layers"][layer]=detail
   if detail["status"]=="REMOTE_IMAGE_VERIFIED":break
  r["status"]="REMOTE_IMAGE_VERIFIED" if r["preferred_layer"] else "NOT_VERIFIED"
  result.append(r)
  if not offline:time.sleep(.1)
 return {"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"service_url":BASE,"total":len(result),"remote_image_verified":sum(x["status"]=="REMOTE_IMAGE_VERIFIED" for x in result),"network_probed":not offline,"records":result,"gatekeeper_note":"Successful JPEG response verifies government-hosted imagery, NOT roof, tree or driveway conditions."}
def main():
 p=argparse.ArgumentParser();p.add_argument("--data-dir",default="evidence/data");p.add_argument("--no-network",action="store_true");p.add_argument("--limit",type=int,default=60)
 a=p.parse_args();d=pathlib.Path(a.data_dir);d.mkdir(parents=True,exist_ok=True)
 out=run(d,a.no_network,max(1,min(60,a.limit)))
 (d/"mngeo_aerial_evidence.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"total":out["total"],"remote_image_verified":out["remote_image_verified"],"network_probed":out["network_probed"]}))
if __name__=="__main__":main()
