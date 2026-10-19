#!/usr/bin/env python3
"""Publish legal-safe, source-backed aerial image availability for the original 60.

Actual JPEG bytes were independently fetched/hashes by the existing rotating
MnGeo WMS crawler. This job validates and links that provenance, without copying
third-party Dakota County/Nearmap pixels into a public commercial repository.
"""
import argparse
import csv
import datetime as dt
import json
import pathlib
import re

TRUSTED="https://imageserver.gisdata.mn.gov/cgi-bin/wmsll?"
HASH=re.compile(r"^[a-f0-9]{64}$",re.I)

def read(directory,name):
    try:
        return json.loads((directory/name).read_text(encoding="utf-8"))
    except (OSError,ValueError):
        return {}

def build(directory):
    with (directory/"kingswood_parcel_candidates.csv").open(encoding="utf-8-sig",newline="") as f:
        seeds=list(csv.DictReader(f))
    if len(seeds)!=60:
        raise ValueError("GateKeeper requires 60 original residential records")
    keys=set()
    for p in seeds:
        key=(str(p.get("parcel_objectid")),str(p.get("county_pin")))
        if not key[0] or not key[1] or key in keys:
            raise ValueError("Missing or duplicate original parcel identity")
        keys.add(key)
    report=read(directory,"fast_validation_report.json")
    feeds={}
    for x in report.get("records",[]):
        key=(str(x.get("parcel_objectid")),str(x.get("county_pin")))
        if key in keys and (key not in feeds or str(x.get("last_checked_utc") or "")>str(feeds[key].get("last_checked_utc") or "")):
            feeds[key]=x
    rows=[]
    for p in seeds:
        id=str(p["parcel_objectid"])
        pin=str(p["county_pin"])
        found=feeds.get((id,pin)) or {}
        src=str(found.get("imagery_source_url") or "")
        digest=str(found.get("imagery_sha256") or "")
        valid=(found.get("imagery")=="GOVERNMENT_REMOTE_JPEG_VERIFIED" and
               src.startswith(TRUSTED) and HASH.fullmatch(digest) is not None and
               isinstance(found.get("imagery_verified_bytes"),int) and found["imagery_verified_bytes"]>150)
        rows.append({
            "parcel_objectid":id,"county_pin":pin,"address":p.get("address"),
            "source_status":"REMOTE_GOVERNMENT_JPEG_LAST_VERIFIED" if valid else "SOURCE_NOT_VALIDATED",
            "source_url":src if valid else None,
            "source_sha256":digest if valid else None,
            "source_checked_at_utc":found.get("last_checked_utc") if valid else None,
            "imagery_layer":found.get("imagery_layer") if valid else None,
            "imagery_year":found.get("imagery_year") if valid else None,
            "locally_downloaded":False,
            "resale_or_redistribution_rights_verified":False,
            "roof_condition_verified":False
        })
    count=sum(x["source_status"]=="REMOTE_GOVERNMENT_JPEG_LAST_VERIFIED" for x in rows)
    return {
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "dataset":"ORIGINAL_KINGS_WOOD_60_REMOTE_AERIAL_SOURCE_REGISTER",
        "source_report_run_utc":report.get("run_utc"),
        "original_parcels":60,
        "remote_jpeg_last_verified":count,
        "local_image_files_published":0,
        "source_availability_complete":count==60,
        "rights_notice":"Dakota County 2025 high-resolution imagery metadata includes Nearmap distribution/commercial-use restrictions; do not mirror third-party image bytes. The linked MnGeo WMS layer is a different source and any further redistribution still needs a source-specific rights check.",
        "verification_notice":"Remote JPEG response hashes are NOT inspections, roof-condition assessments or verified completed permits.",
        "records":rows
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--data-dir",type=pathlib.Path,default=pathlib.Path("evidence/data"))
    args=parser.parse_args()
    result=build(args.data_dir)
    out=args.data_dir/"imagery_source_availability.json"
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"remote_images_last_verified":result["remote_jpeg_last_verified"],"local_image_files_published":0,"original_parcels":60}))
    if result["remote_jpeg_last_verified"]!=60:
        raise SystemExit("Not all original 60 WMS responses have verified hashes; source availability is incomplete")

if __name__=="__main__":
    main()
