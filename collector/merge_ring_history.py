#!/usr/bin/env python3
"""Recover ALL real previously-published official ArcGIS ring parcels.
A larger geographic radius must never silently erase prior authenticated GIS
candidates. Archived source observations remain explicitly tagged for recheck.

Reads local Git history; no external API bypass, no synthesized parcel records.
"""
from __future__ import annotations
import copy, json, pathlib, subprocess

PATH="evidence/data/outward_ring_candidates.json"
OFFICIAL="https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2/query"

def qualified(snapshot):
    return (isinstance(snapshot,dict) and snapshot.get("source")==OFFICIAL and
        snapshot.get("source_query_completed") is True and not snapshot.get("errors") and
        snapshot.get("seed_count")==60 and isinstance(snapshot.get("ring_candidates"),list))

def prior_snapshots(limit=60):
    """Use fully fetched immutable committed source evidence; do not trust shallow clones."""
    try:
        result=subprocess.run(["git","log","--format=%H","-n",str(limit),"--",PATH],
          check=True,capture_output=True,text=True,timeout=20)
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        return []
    found=[]
    for sha in (x.strip() for x in result.stdout.splitlines()):
        if not sha:continue
        try:
            raw=subprocess.run(["git","show",sha+":"+PATH],check=True,capture_output=True,
                text=True,timeout=10).stdout
            parsed=json.loads(raw)
            if qualified(parsed):found.append((sha,parsed))
        except (OSError,ValueError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
            continue
    return found

def merge(current,historical):
    if not qualified(current):raise ValueError("Current official GIS source query incomplete")
    # Maintain identity by BOTH county PIN and ArcGIS OBJECTID; never merge conflicting parcels.
    pins={};by_id={};original_count=len(current["ring_candidates"])
    for sha,snapshot in [(None,current)]+list(historical):
        if not qualified(snapshot):continue
        for p in snapshot["ring_candidates"]:
            if not isinstance(p,dict):raise ValueError("Invalid published official parcel")
            pin=str(p.get("county_pin") or "");oid=str(p.get("parcel_objectid") or "")
            url=str(p.get("source_record_url") or "")
            if not(pin.isdigit() and oid.isdigit() and url.startswith(OFFICIAL) and
                  isinstance(p.get("center_lat"),(int,float)) and
                  isinstance(p.get("center_lon"),(int,float))):
                raise ValueError("Invalid archived official parcel provenance")
            if oid in by_id and by_id[oid]!=pin:raise ValueError("Conflicting official GIS ID -> PIN")
            if pin in pins:
                if str(pins[pin]["parcel_objectid"])!=oid:raise ValueError("Conflicting official GIS PIN -> ID")
                # Current run wins; older versions cannot downgrade verified attributes.
                old=pins[pin]
                if not old.get("bbox_4326") and p.get("bbox_4326"):
                    old["bbox_4326"]=p["bbox_4326"]
                continue
            by_id[oid]=pin
            record=copy.deepcopy(p)
            record["observed_in_current_source_query"]=sha is None
            if sha is not None:
                record["retained_historical_official_observation"]=True
                record["last_historical_source_observation_utc"]=snapshot.get("generated_at_utc")
                record["historical_source_commit"]=sha
            else:record["retained_historical_official_observation"]=False
            pins[pin]=record
    all_records=sorted(pins.values(),key=lambda p:(int(p.get("ring") or 999),
         float(p.get("distance_from_seed_center_m") or 0),str(p["county_pin"])))
    merged=copy.deepcopy(current)
    merged["ring_candidates"]=all_records
    merged["candidate_count"]=len(all_records)
    merged["counts_by_ring"]={str(n):sum(int(x.get("ring") or -1)==n for x in all_records)
                              for n in sorted({int(x.get("ring") or 0) for x in all_records})}
    merged["historical_source_reconciliation"]={
       "observed_in_current_query":original_count,
       "historical_official_records_retained":len(all_records)-original_count,
       "distinct_source_linked_records":len(all_records),
       "historical_commits_checked":len(historical),
       "any_missing_from_current_query_requires_recheck":len(all_records)>original_count,
       "note":"Earlier official GIS query records preserved despite changes in query pagination; retained entries are not claimed as freshly checked."
    }
    if len(all_records)<original_count:raise ValueError("Historical merge dropped queried parcels")
    return merged
