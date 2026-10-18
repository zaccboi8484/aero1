#!/usr/bin/env python3
"""Opt-in Groq permit-text extraction from AeroLeadAI v1.4.

NOT a crawler, proof of a permit, published Mindex score, or an automatic source
of truth. Never scheduled. A human must explicitly authorize sharing text with
a third-party provider before any API call. Input is a JSON list of {ref,text}.
Proposals cannot set verified=True even if the model asks them to.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

URL = "https://api.groq.com/openai/v1/chat/completions"
SYSTEM = ("Extract only statements explicitly present in the permit text. "
 "Return JSON keys is_roof_permit (boolean/null), permit_date (ISO date/null), "
 "permit_type (string/null), address (string/null), confidence (0..1). "
 "If absent, use null. The output is an unverified proposal.")
MAX_ITEMS = 20
MAX_TEXT = 2000

def clean(raw):
    try:
        obj = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    confidence = obj.get("confidence")
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
        if confidence != confidence: confidence = 0.0  # Reject NaN.
    except (ValueError, TypeError, OverflowError):
        confidence = 0.0
    date = obj.get("permit_date")
    if date is not None:
        try:
            date = dt.date.fromisoformat(str(date)).isoformat()
        except ValueError:
            date = None
    roof = obj.get("is_roof_permit")
    return {
        "is_roof_permit":roof if isinstance(roof, bool) else None,
        "permit_date":date,
        "permit_type":obj.get("permit_type")[:160] if isinstance(obj.get("permit_type"),str) else None,
        "address":obj.get("address")[:180] if isinstance(obj.get("address"),str) else None,
        "confidence":confidence,
        "verified":False,
        "status":"UNVERIFIED_PROPOSAL"
    }

def call_groq(text,key,model,opener=urllib.request.urlopen):
    body = json.dumps({"model":model,"temperature":0,"response_format":{"type":"json_object"},
     "messages":[{"role":"system","content":SYSTEM},{"role":"user","content":text[:MAX_TEXT]}]}).encode()
    req=urllib.request.Request(URL,data=body,headers={
        "Authorization":"Bearer "+key,"Content-Type":"application/json",
        "Accept":"application/json"},method="POST")
    with opener(req,timeout=20) as response:
        wrapper=json.loads(response.read(60000))
    return wrapper["choices"][0]["message"]["content"]

def run(rows,key,model,opener=urllib.request.urlopen,pause=3.0):
    if not isinstance(rows,list) or len(rows)>MAX_ITEMS:
        raise ValueError("Maximum 20 proposals per invocation; no bulk third-party transfer")
    if not key or not model:
        raise ValueError("Provider key and model required")
    results=[]
    for i,row in enumerate(rows):
        if not isinstance(row,dict) or not isinstance(row.get("text"),str):
            raise ValueError("Every row must contain explicit text")
        source=row["text"][:MAX_TEXT]
        try:
            proposed=clean(call_groq(source,key,model,opener))
            error=None if proposed else "BAD_MODEL_OUTPUT"
        except (urllib.error.URLError,KeyError,ValueError,TimeoutError,OSError,IndexError,TypeError) as exc:
            proposed=None
            error=type(exc).__name__
        results.append({"ref":str(row.get("ref") or "")[:120],
          "source_sha256":hashlib.sha256(source.encode()).hexdigest(),
          "proposal":proposed,"error":error,"model":model,
          "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
          "human_and_original_issuer_review_required":True})
        if pause>0 and i<len(rows)-1:time.sleep(pause)
    return results

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in",dest="source",required=True)
    parser.add_argument("--out",required=True,help="New file only; no overwrite")
    parser.add_argument("--send-to-groq",action="store_true",
      help="Explicitly authorize external processing of supplied text")
    ns=parser.parse_args()
    if not ns.send_to_groq:
        parser.error("External API disabled: --send-to-groq must be supplied")
    key=os.environ.get("GROQ_API_KEY")
    model=os.environ.get("GROQ_MODEL")
    if not key or not model:
        parser.error("GROQ_API_KEY and GROQ_MODEL must be set server-side")
    rows=json.loads(pathlib.Path(ns.source).read_text(encoding="utf-8"))
    results=run(rows,key,model)
    receipt={"lane":"optional_groq_extract","all_unverified":True,"records_processed":len(results),
        "results":results}
    with pathlib.Path(ns.out).open("x",encoding="utf-8") as target:
        json.dump(receipt,target,indent=2)
        target.write("\n")
    print(json.dumps({"processed":len(results),"unverified_proposals":sum(x["proposal"] is not None for x in results),
      "errors":sum(x["error"] is not None for x in results)}))

if __name__=="__main__":
    main()
