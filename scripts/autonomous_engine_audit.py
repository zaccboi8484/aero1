#!/usr/bin/env python3
"""Independent evidence engine. Audits candidate completeness without inventing permits, owners or roof damage."""
import datetime,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
SOURCE=ROOT/"autonomous_residential_discovery.json"
DEST=ROOT/"autonomous_engine_audit.json"
FIELDS=("permit_history_verified","storm_source_verified","roof_imagery_reviewed","valuation_verified","recorded_owner_verified","single_family_verified")
def main():
    if not SOURCE.exists(): raise SystemExit("Discovery evidence missing; cannot produce an audit")
    data=json.loads(SOURCE.read_text()); records=data.get("records")
    if not isinstance(records,list): raise ValueError("records must be a list")
    seen=set(); gaps={k:0 for k in FIELDS}; duplicates=0; missing_pin=0; candidates=[]
    for p in records:
        pin=str(p.get("county_pin") or "").strip()
        if not pin: missing_pin+=1; continue
        if pin in seen: duplicates+=1; continue
        seen.add(pin)
        missing=[k for k in FIELDS if p.get(k) is not True]
        for k in missing: gaps[k]+=1
        candidates.append({"county_pin":pin,"unverified_evidence":missing})
    if duplicates or missing_pin:
        raise ValueError(f"Identity integrity failed: duplicates={duplicates}, missing_pin={missing_pin}")
    report={"format":"AERO_ENGINE_AUDIT_V1","generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "discovery_checkpoint_utc":data.get("last_completed_at_utc"),"unique_properties":len(seen),
        "unverified_by_type":gaps,"readiness":"EVIDENCE_INCOMPLETE" if any(gaps.values()) else "COVERAGE_COMPLETE",
        "meaning":"Source coverage audit only; unverified means unknown, not absent or damaged.",
        "properties_needing_enrichment":candidates}
    DEST.parent.mkdir(parents=True,exist_ok=True)
    temp=DEST.with_suffix(".tmp");temp.write_text(json.dumps(report,indent=2)+"\n");temp.replace(DEST)
    print(json.dumps({"properties":len(seen),"missing_evidence":gaps}))
if __name__=="__main__": main()
