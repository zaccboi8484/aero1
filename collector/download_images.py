#!/usr/bin/env python3
"""Download up to 60 actual Dakota County orthophotos. No substitute images.
Requires an existing source geometry manifest; verifies JPEG headers and sizes.
GitHub Actions runs this collector, then commits images and validated inventory.
"""
import concurrent.futures,datetime,hashlib,json,pathlib,time,urllib.request,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"evidence/data/imagery_manifest.json"
OUTPUT=ROOT/"evidence/images"
INDEX=ROOT/"evidence/data/imagery_downloads.json"
YEAR="2025-spring-leaf-off"
MAX_BYTES=3*1024*1024
OUTPUT.mkdir(parents=True,exist_ok=True)
meta=json.loads(SOURCE.read_text(encoding="utf-8"))
records=meta.get("records",[])[:60]
def fetch(record):
    parcel=str(record["parcel_objectid"])
    url=record.get("image_layers",{}).get(YEAR)
    if not url or not url.startswith("https://gisimg.co.dakota.mn.us/arcgis/rest/services/AerialPhotography/"):
        return {"parcel_objectid":parcel,"status":"UNAVAILABLE","reason":"missing approved county URL"}
    file=OUTPUT/(parcel+"-2025-spring.jpg")
    if file.exists():
        content=file.read_bytes()
        if content[:3]==b"\xff\xd8\xff" and content[-2:]==b"\xff\xd9":
            return {"parcel_objectid":parcel,"address":record["address"],"status":"DOWNLOADED","file":"/evidence/images/"+file.name,"sha256":hashlib.sha256(content).hexdigest(),"bytes":len(content),"source_url":url,"source_year":"2025","source_provider":"Dakota County GIS","acquisition_status":"remote image response validated"}
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-KingsWood-Imagery-Indexer/1.0","Accept":"image/jpeg"})
            with urllib.request.urlopen(req,timeout=40) as response:
                mime=response.headers.get("content-type","").lower()
                if "image/jpeg" not in mime and "image/jpg" not in mime:raise RuntimeError("County returned "+mime)
                data=response.read(MAX_BYTES+1)
            if len(data)>MAX_BYTES or len(data)<1000:raise RuntimeError("Image size out of range")
            if not(data[:3]==b"\xff\xd8\xff" and data[-2:]==b"\xff\xd9"):raise RuntimeError("Invalid JPEG signature")
            tmp=file.with_suffix(".tmp");tmp.write_bytes(data);tmp.replace(file)
            return {"parcel_objectid":parcel,"address":record["address"],"status":"DOWNLOADED","file":"/evidence/images/"+file.name,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),"source_url":url,"source_year":"2025","source_provider":"Dakota County GIS","acquisition_status":"remote image response validated"}
        except Exception as e:
            reason=str(e)[:180]
            if attempt<2:time.sleep(1+attempt*2)
    return {"parcel_objectid":parcel,"address":record["address"],"status":"FAILED","reason":reason,"source_url":url}
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for result in pool.map(fetch,records):
        results.append(result)
        print(result["parcel_objectid"],result["status"],flush=True)
success=sum(r["status"]=="DOWNLOADED" for r in results)
INDEX.write_text(json.dumps({"downloaded_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"requested":len(records),"downloaded":success,"failed":len(records)-success,"source_collection":"Dakota County 2025 Spring Leaf-Off ImageServer","note":"Only success-marked images are locally retained original remote JPEG bytes. Missing properties show no image. County attribution required; no property condition inferred.","records":results},indent=2)+"\n",encoding="utf-8")
print("Downloaded",success,"of",len(records))
if success==0:raise SystemExit("No actual imagery downloaded; failing workflow rather than reporting false success")
