#!/usr/bin/env python3
"""Restore accidentally dropped prior *real* GIS source observations from Git history.

No fake evidence, no force-push, no regression in newer observations.
One-time recovery commit pinned to the independently inspected Oct 22 report.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import pathlib
import subprocess

DATA=pathlib.Path("evidence/data")
PRIOR_SHA="0871b24f6cb6d401f186395201edf1d27c265e30"

def merge_reports(current,prior):
    if not isinstance(current.get("records"),list) or not isinstance(prior.get("records"),list):
        raise ValueError("Both recovered source reports must contain actual observation lists")
    merged={}
    for report in (prior,current):
        for row in report["records"]:
            if not isinstance(row,dict) or not row.get("county_pin") or not row.get("parcel_objectid"):
                raise ValueError("Missing original GIS parcel identity; cannot safely recover")
            pin=str(row["county_pin"])
            old=merged.get(pin)
            if old and str(old.get("parcel_objectid"))!=str(row["parcel_objectid"]):
                raise ValueError("Conflicting parcel identity for county PIN "+pin)
            if not old or str(row.get("last_checked_utc") or "")>=str(old.get("last_checked_utc") or ""):
                merged[pin]=row
    active=int(current.get("total_indexed") or 0)
    if active<0:raise ValueError("Invalid active parcel count")
    result={**current}
    result["records"]=[merged[k] for k in sorted(merged)]
    result["historical_source_recovery"]={
        "at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit":PRIOR_SHA,
        "prior_record_count":len(prior["records"]),
        "current_record_count_before_recovery":len(current["records"]),
        "merged_record_count":len(merged),
        "recovered_observations":len(merged)-len(current["records"]),
        "notes":"Only pre-existing official source observations are restored. Newer observations win. No municipal or roof certification inferred."
    }
    if len(merged)<len(current["records"]):raise ValueError("Data preservation regression")
    return result

def main():
    args=argparse.ArgumentParser()
    args.add_argument("--previous-commit",default=PRIOR_SHA)
    args.add_argument("--data-dir",type=pathlib.Path,default=DATA)
    options=args.parse_args()
    present=json.loads((options.data_dir/"fast_validation_report.json").read_text(encoding="utf-8"))
    prior=json.loads(subprocess.check_output(
        ["git","show",options.previous_commit+":evidence/data/fast_validation_report.json"],
        text=True))
    updated=merge_reports(present,prior)
    if updated["historical_source_recovery"]["recovered_observations"]<0:
        raise SystemExit("Refusing historical source downgrade")
    (options.data_dir/"fast_validation_report.json").write_text(json.dumps(updated,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(updated["historical_source_recovery"],indent=2))

if __name__=="__main__":main()
