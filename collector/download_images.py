#!/usr/bin/env python3
"""Download authentic county JPEGs through shared GateKeeper policy and audit."""
import datetime,hashlib,json,pathlib
from evidence_audit import load as load_audit,save as save_audit
from gatekeeper_fetch import fetch_source
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/images";OUT.mkdir(parents=True,exist_ok=True)
DATA=ROOT/"evidence/data"
records=json.loads((DATA/"imagery_manifest.json").read_text())["records"][:60]
audit=load_audit();results=[]
for parcel in records:
    oid=str(parcel["parcel_objectid"]);url=parcel.get("image_layers",{}).get("2025-spring-leaf-off")
    file=OUT/(oid+"-2025-spring.jpg")
    item={"parcel_objectid":oid,"address":parcel["address"],"source_url":url,"status":"FAILED"}
    try:
        if not url:raise ValueError("No official image URL")
        original=file.read_bytes() if file.exists() else None
        if original and original[:3]==bytes.fromhex("ffd8ff") and original[-2:]==bytes.fromhex("ffd9"):
            body=original
        else:
            response=fetch_source(audit,source="dakota-aerial-2025-leaf-off",source_id=oid,
                                  url=url,territory="kings-wood-001",ttl_hours=168)
            body=response.get("body")
            if not body:raise ValueError(response.get("error") or response["status"])
            if body[:3]!=bytes.fromhex("ffd8ff") or body[-2:]!=bytes.fromhex("ffd9"):
                raise ValueError("Source returned invalid JPEG bytes")
            file.write_bytes(body)
        item.update({"status":"DOWNLOADED","file":"/evidence/images/"+file.name,
          "sha256":hashlib.sha256(body).hexdigest(),"bytes":len(body),"source_year":"2025"})
    except Exception as error:item["reason"]=str(error)[:220]
    results.append(item);print(oid,item["status"],flush=True)
    save_audit(audit)
n=sum(r["status"]=="DOWNLOADED" for r in results)
(DATA/"imagery_downloads.json").write_text(json.dumps({"retrieved_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "requested":len(results),"downloaded":n,"failed":len(results)-n,"records":results},indent=2)+"\n")
print("Verified saved images:",n,"/",len(results))
if not n:raise SystemExit("No validated image bytes; inspect audit error records")
