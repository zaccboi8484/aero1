#!/usr/bin/env python3
"""Publish a small, source-attributed GateKeeper heartbeat for the live UI.

The scheduled validator owns the source report. This module observes it and
never marks a permit document, roof condition or Mindex as independently verified.
No API key, external provider call, or new parcel is required.
"""
import datetime as dt
import json
import pathlib
import argparse

def read_json(directory,name):
    try:
        value=json.loads((directory/name).read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}

def summarise(data_dir):
    report=read_json(data_dir,"fast_validation_report.json")
    audit=read_json(data_dir,"municipal_permit_export_audit.json")
    release=read_json(data_dir,"gatekeeper_release_truth.json")
    records=report.get("records",[])
    if not isinstance(records,list):
        records=[]
    municipal=report.get("municipal_permit_source") or {}
    if not isinstance(municipal,dict):
        municipal={}
    portal=municipal.get("status") or "NOT_CHECKED"
    counts={
        "indexed_parcels":report.get("total_indexed") if isinstance(report.get("total_indexed"),int) else None,
        "parcels_checked_last_run":report.get("batch_attempted") if isinstance(report.get("batch_attempted"),int) else 0,
        "records_in_source_ledger":len(records),
        "parcels_checked_at_least_once":report.get("checked_total",len(records)),
        "parcels_not_yet_checked":report.get("remaining_unchecked",max(0,(report.get("total_indexed") or 0)-len(records))),
        "research_batch_requested":report.get("batch_requested",report.get("batch_attempted",0)),
        "official_pin_matches_in_ledger":sum(r.get("parcel_validation")=="OFFICIAL_PIN_CONFIRMED" for r in records if isinstance(r,dict)),
        "government_jpeg_response_records":sum(r.get("imagery")=="GOVERNMENT_REMOTE_JPEG_VERIFIED" for r in records if isinstance(r,dict)),
        "municipal_report_matches":len(audit.get("records",[])) if isinstance(audit.get("records"),list) else 0,
        "permit_documents_reviewed":0,
        "human_verified_roof_conditions":0
    }
    run_at=report.get("run_utc")
    return {
        "format":"GATEKEEPER_SOURCE_HEARTBEAT_V1",
        "published_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_report_run_utc":run_at if isinstance(run_at,str) else None,
        "source_data_present":bool(run_at) and isinstance(report.get("records"),list),
        "municipal_portal_status":portal,
        "municipal_portal_access_blocked":portal=="PUBLIC_SOURCE_UNAVAILABLE",
        "municipal_portal_error":str(municipal.get("error") or "")[:150] or None,
        "counts":counts,
        "release_certified":bool(release.get("release_certified")) if isinstance(release.get("release_certified"),bool) else False,
        "publication_is_not_new_permit_discovery":True,
        "no_unreviewed_condition_claims":True,
        "note":"Source-health heartbeat is not a completed municipal permit review, physical roof inspection or released Mindex."
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--data-dir",type=pathlib.Path,default=pathlib.Path("evidence/data"))
    args=parser.parse_args()
    p=summarise(args.data_dir)
    if not p["source_data_present"]:
        raise SystemExit("GateKeeper: no valid source report available; heartbeat not published")
    target=args.data_dir/"source_health_public.json"
    target.write_text(json.dumps(p,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"source_run_utc":p["source_report_run_utc"],"portal":p["municipal_portal_status"],"matches":p["counts"]["municipal_report_matches"],"source_data_present":True}))

if __name__=="__main__":main()
