#!/usr/bin/env python3
"""Shared durable evidence ledger for all Dakota County territories.
Uses a checked-in JSON checkpoint until Supabase is configured.
No evidence is invented. Atomic writes; single-writer GitHub Actions concurrency required.
"""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,os,pathlib,tempfile,urllib.parse

ROOT=pathlib.Path(__file__).resolve().parents[1]
FILE=ROOT/"evidence/data/evidence_audit_index.json"
TERRITORIES={"kings-wood-001":"eagan","burnsville-expansion":"burnsville","dakota-county":"dakota_county"}
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def canonical_url(url):
    parsed=urllib.parse.urlsplit(str(url or ""))
    if parsed.scheme!="https" or not parsed.netloc:raise ValueError("HTTPS source URL required")
    query=urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(parsed.query,keep_blank_values=True)))
    return urllib.parse.urlunsplit(("https",parsed.netloc.lower(),parsed.path,query,""))
def fingerprint(source,source_id):
    if not source or not source_id:raise ValueError("Source and original source record ID required")
    return hashlib.sha256((source+"\x1f"+source_id).encode()).hexdigest()
def load(path=FILE):
    if path.exists():return json.loads(path.read_text(encoding="utf-8"))
    return {"schema":1,"sources":{},"content_hashes":{},"territories":{
      "dakota-county":{"name":"Dakota County","jurisdiction":"dakota_county","parent":None},
      "kings-wood-001":{"name":"Kings Wood · Eagan","jurisdiction":"eagan","parent":"dakota-county"},
      "burnsville-expansion":{"name":"Burnsville Expansion","jurisdiction":"burnsville","parent":"dakota-county"}},"history":[]}
def save(db,path=FILE):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix="audit-",suffix=".tmp")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(db,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.remove(tmp)
def review(db,*,source,source_id,url,territory,sha256=None,etag=None,last_modified=None,min_hours=168):
    if territory not in TERRITORIES:raise ValueError("Unknown territory")
    url=canonical_url(url);key=fingerprint(source,source_id);item=db["sources"].get(key)
    if item and item.get("canonical_url")!=url:
        # Same record may change URLs: request review instead of silently trusting new endpoint.
        action="REVIEW_URL_CHANGE"
    elif sha256 and item and item.get("sha256")==sha256 and item.get("status")=="ACQUIRED":
        action="SKIP_UNCHANGED"
    elif sha256 and sha256 in db["content_hashes"] and db["content_hashes"][sha256]!=key:
        action="SKIP_DUPLICATE"
    elif item and item.get("status")=="ACQUIRED" and (etag or last_modified):
        action="CONDITIONAL_GET"
    elif item and item.get("status")=="ACQUIRED":
        try:
            age=dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(item["checked_at"])
            action="SKIP_RECENT" if age.total_seconds()<min_hours*3600 else "FETCH"
        except (ValueError,KeyError):action="FETCH"
    else:action="FETCH"
    if item:
        links=item.setdefault("territories",[])
        if territory not in links:links.append(territory)
    db["history"].append({"timestamp":utc(),"action":action,"source_key":source,"source_record_id":source_id,"territory":territory,"url":url})
    return {"key":key,"action":action,"if_none_match":item.get("etag") if item else None,"if_modified_since":item.get("last_modified") if item else None}
def record(db,*,source,source_id,url,territory,status,sha256=None,etag=None,last_modified=None,size=None,error=None):
    if status not in ("ACQUIRED","NOT_MODIFIED","FAILED","RESTRICTED"):raise ValueError("Unknown status")
    if territory not in TERRITORIES:raise ValueError("Unknown territory")
    url=canonical_url(url);key=fingerprint(source,source_id)
    item=db["sources"].get(key,{})
    if item.get("canonical_url") and item["canonical_url"]!=url:raise ValueError("Changed source URL must be reviewed before recording")
    if sha256:
        if len(sha256)!=64 or any(c not in "0123456789abcdef" for c in sha256):raise ValueError("Invalid SHA256")
        other=db["content_hashes"].get(sha256)
        if other and other!=key:
            db["history"].append({"timestamp":utc(),"action":"SKIP_DUPLICATE","source_key":source,"source_record_id":source_id,"territory":territory,"duplicate_of":other})
            return False
    links=set(item.get("territories",[]));links.add(territory)
    item.update({"source_key":source,"source_record_id":source_id,"canonical_url":url,
      "territories":sorted(links),"checked_at":utc(),"status":"ACQUIRED" if status=="NOT_MODIFIED" and item.get("status")=="ACQUIRED" else status})
    if sha256:
        item["sha256"]=sha256
        db["content_hashes"][sha256]=key
    if etag:item["etag"]=etag
    if last_modified:item["last_modified"]=last_modified
    if size is not None:item["bytes"]=int(size)
    db["sources"][key]=item
    db["history"].append({"timestamp":utc(),"action":status,"source_key":source,"source_record_id":source_id,"territory":territory,"sha256":sha256,"error":error})
    return True
if __name__=="__main__":
    p=argparse.ArgumentParser(description="Inspect shared source-audit counts")
    p.add_argument("--file",type=pathlib.Path,default=FILE)
    args=p.parse_args();d=load(args.file)
    print(json.dumps({"sources":len(d["sources"]),"unique_hashes":len(d["content_hashes"]),"events":len(d["history"]),"territories":list(d["territories"])},indent=2))
