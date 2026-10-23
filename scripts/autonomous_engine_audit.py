#!/usr/bin/env python3
"""Audit parcel evidence without turning bad individual records into a stalled job."""
import datetime
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "data"
SOURCE = ROOT / "autonomous_residential_discovery.json"
DEST = ROOT / "autonomous_engine_audit.json"
FIELDS = (
    "permit_history_verified", "storm_source_verified", "roof_imagery_reviewed",
    "valuation_verified", "recorded_owner_verified", "single_family_verified",
)

def main():
    if not SOURCE.exists():
        raise SystemExit("Discovery evidence missing: cannot audit; source job needs attention")
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError("Discovery records must be a list")

    seen = set()
    gaps = {key: 0 for key in FIELDS}
    candidates = []
    quarantined = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            quarantined.append({"index": index, "reason": "not_an_object"})
            continue
        pin = str(record.get("county_pin") or "").strip()
        if not pin:
            quarantined.append({"index": index, "reason": "missing_county_pin"})
            continue
        if pin in seen:
            quarantined.append({"index": index, "reason": "duplicate_county_pin", "county_pin": pin})
            continue
        seen.add(pin)
        missing = [key for key in FIELDS if record.get(key) is not True]
        for key in missing:
            gaps[key] += 1
        candidates.append({"county_pin": pin, "unverified_evidence": missing})

    report = {
        "format": "AERO_ENGINE_AUDIT_V2",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "discovery_checkpoint_utc": data.get("last_completed_at_utc"),
        "source_records": len(records),
        "unique_properties": len(seen),
        "quarantined_count": len(quarantined),
        "quarantined_records": quarantined,
        "unverified_by_type": gaps,
        "readiness": "IDENTITY_REVIEW_REQUIRED" if quarantined else (
            "EVIDENCE_INCOMPLETE" if any(gaps.values()) else "COVERAGE_COMPLETE"
        ),
        "meaning": "Unknown evidence is not evidence of absence or roof damage. Quarantined entries are never promoted.",
        "properties_needing_enrichment": candidates,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    temp = DEST.with_suffix(".tmp")
    temp.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temp.replace(DEST)
    print(json.dumps({
        "unique_properties": len(seen), "quarantined": len(quarantined),
        "unverified_by_type": gaps, "readiness": report["readiness"],
    }))
    if quarantined:
        print("WARNING: Invalid/duplicate records quarantined. Review audit artifact.")

if __name__ == "__main__":
    main()
