#!/usr/bin/env python3
"""GateKeeper HTTP fetch controller: allowlisted official domains, conditional fetch,
bounded retries, dedupe, and evidence audit. Never bypass restrictions.
Standard library only. Use from source-specific collectors.
"""
from __future__ import annotations
import hashlib,ipaddress,json,random,socket,time,urllib.error,urllib.parse,urllib.request
from evidence_audit import review,record,canonical_url
HOSTS={"arcgis.metc.state.mn.us","gisimg.co.dakota.mn.us","gis.co.dakota.mn.us",
       "gis.cityofeagan.com","eagan.onlama.com","www.burnsvillemn.gov",
       "burnsvillemn.gov","dakotacountymn.gov","www.dakotacountymn.gov"}
class FetchRejected(Exception):pass
class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)
def validate_url(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme!="https" or u.username or u.password or u.port not in (None,443):raise FetchRejected("HTTPS only; no credentials or unusual ports")
    if (u.hostname or "").lower() not in HOSTS:raise FetchRejected("Unapproved source host")
    return canonical_url(url)
def fetch_source(ledger,*,source,source_id,url,territory,max_bytes=4_000_000,ttl_hours=168):
    url=validate_url(url)
    decision=review(ledger,source=source,source_id=source_id,url=url,territory=territory,min_hours=ttl_hours)
    if decision["action"].startswith("SKIP") or decision["action"]=="REVIEW_URL_CHANGE":
        return {"status":decision["action"],"body":None}
    headers={"User-Agent":"AeroLeadAI-GateKeeper/1.0 (official source acquisition)",
             "Accept":"application/json,image/jpeg,application/pdf,text/csv,*/*;q=0.2"}
    if decision.get("if_none_match"):headers["If-None-Match"]=decision["if_none_match"]
    if decision.get("if_modified_since"):headers["If-Modified-Since"]=decision["if_modified_since"]
    opener=urllib.request.build_opener(_SafeRedirect())
    for attempt in range(3):
        try:
            request=urllib.request.Request(url,headers=headers)
            with opener.open(request,timeout=25) as response:
                kind=(response.headers.get("Content-Type") or "").lower()
                length=response.headers.get("Content-Length")
                if length and int(length)>max_bytes:raise FetchRejected("Source exceeds byte budget")
                body=response.read(max_bytes+1)
                if len(body)>max_bytes:raise FetchRejected("Source exceeds byte budget")
                if not body:raise FetchRejected("Empty source response")
                if "text/html" in kind:raise FetchRejected("HTML is not accepted as evidence payload")
                sha=hashlib.sha256(body).hexdigest()
                etag=response.headers.get("ETag");modified=response.headers.get("Last-Modified")
            record(ledger,source=source,source_id=source_id,url=url,territory=territory,
                   status="ACQUIRED",sha256=sha,etag=etag,last_modified=modified,size=len(body))
            return {"status":"ACQUIRED","body":body,"sha256":sha,"content_type":kind}
        except urllib.error.HTTPError as e:
            if e.code==304:
                record(ledger,source=source,source_id=source_id,url=url,territory=territory,status="NOT_MODIFIED")
                return {"status":"NOT_MODIFIED","body":None}
            if e.code in (401,403,404):
                record(ledger,source=source,source_id=source_id,url=url,territory=territory,
                       status="RESTRICTED" if e.code in (401,403) else "FAILED",error="HTTP "+str(e.code))
                return {"status":"RESTRICTED" if e.code in (401,403) else "FAILED","body":None}
            last="HTTP "+str(e.code)
        except (urllib.error.URLError,TimeoutError,OSError,FetchRejected) as e:
            last=str(e)
            if isinstance(e,FetchRejected):break
        if attempt<2:time.sleep((1.5**attempt)+random.random())
    record(ledger,source=source,source_id=source_id,url=url,territory=territory,status="FAILED",error=last[:300])
    return {"status":"FAILED","body":None,"error":last[:300]}
