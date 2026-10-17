#!/usr/bin/env python3
"""Dakota County aerial source diagnostics; only verified source bytes count.
No images or copyrighted imagery are redistributed in GitHub. This probes
authorized public ArcGIS exportImage endpoints, records response status and
SHA-256, and offers original county-hosted links when accessible.
"""
import json,urllib.request,urllib.parse,urllib.error,pathlib,hashlib,time,datetime
DIR=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(name,default):
 try:return json.loads((DIR/name).read_text(encoding="utf-8"))
 except (OSError,ValueError):return default
manifest=read("imagery_manifest.json",{})
old=read("imagery_source_probe.json",{})
previous={str(x.get("parcel_objectid")):x for x in old.get("records",[])}
records=[]
source_host="gisimg.co.dakota.mn.us"
def request(url,accept,limit=2_000_000):
 p=urllib.parse.urlparse(url)
 if p.scheme!="https" or p.hostname!=source_host:raise ValueError("Non-county service URL rejected")
 req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-EvidenceCollector/1.0 (small image export verification)","Accept":accept})
 with urllib.request.urlopen(req,timeout=8) as response:
  code=response.status;mime=response.headers.get("Content-Type","")
  data=response.read(limit+1)
  if len(data)>limit:raise ValueError("Source response exceeds 2 MB")
  return code,mime,data
def sniff_jpeg(b):return len(b)>100 and b[:3]==b"\xff\xd8\xff" and b[-2:]==b"\xff\xd9"
consecutive_errors=0
started=time.monotonic()
for i,p in enumerate(manifest.get("records",[])):
 oid=str(p.get("parcel_objectid",""))
 source=(p.get("image_layers") or {}).get("2025-spring-leaf-off")
 row={"parcel_objectid":oid,"source_url":source,"checked_utc":NOW,
  "status":"NOT_CHECKED","response_type":None,"bytes":0,"sha256":None,"image_link":None}
 if not source:
  row["status"]="MISSING_SERVICE_URL";records.append(row);continue
 if consecutive_errors>=3 or time.monotonic()-started>140:
  row["status"]="DEFERRED_SOURCE_CIRCUIT_OPEN"
  if oid in previous and previous[oid].get("status")=="REMOTE_IMAGE_AVAILABLE":
   row["previous_verified"]=previous[oid].get("checked_utc")
  records.append(row);continue
 try:
  # First, request a server response containing the image as a JPEG.
  direct=source
  status,mime,payload=request(direct,"image/jpeg,application/octet-stream,*/*")
  if sniff_jpeg(payload):
   row.update({"status":"REMOTE_IMAGE_AVAILABLE","response_type":mime,"bytes":len(payload),
    "sha256":hashlib.sha256(payload).hexdigest(),"image_link":direct})
  else:
   # Fallback: ArcGIS f=json may return a signed or generated image URL.
   parsed=urllib.parse.urlparse(source)
   params=urllib.parse.parse_qsl(parsed.query,keep_blank_values=True)
   parameters=[(k,("json" if k=="f" else v)) for k,v in params]
   if not any(k=="f" for k,_ in parameters):parameters.append(("f","json"))
   meta_url=urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(parameters)))
   _,_,meta_bytes=request(meta_url,"application/json",limit=200_000)
   metadata=json.loads(meta_bytes)
   href=str(metadata.get("href",""))
   if not href:raise ValueError("No JPEG body and exportImage metadata has no href")
   status,mime,payload=request(href,"image/jpeg,application/octet-stream,*/*")
   if not sniff_jpeg(payload):raise ValueError("County image href did not return valid JPEG bytes")
   row.update({"status":"REMOTE_IMAGE_AVAILABLE","response_type":mime,"bytes":len(payload),
    "sha256":hashlib.sha256(payload).hexdigest(),"image_link":href})
  consecutive_errors=0
 except Exception as e:
  consecutive_errors+=1
  row.update({"status":"SOURCE_ERROR","reason":str(e)[:220]})
 records.append(row)
 if i<len(manifest.get("records",[]))-1:time.sleep(0.12)
result={"checked_at_utc":NOW,"total":len(records),
 "remote_jpegs_verified":sum(x.get("status")=="REMOTE_IMAGE_AVAILABLE" for x in records),
 "errors":sum(x.get("status")=="SOURCE_ERROR" for x in records),
 "deferred":sum(x.get("status")=="DEFERRED_SOURCE_CIRCUIT_OPEN" for x in records),
 "records":records,"note":"No original JPEGs uploaded. Validated bytes verify remote service availability only, NOT physical defects or permission to redistribute."}
(DIR/"imagery_source_probe.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k!="records"},indent=2))
