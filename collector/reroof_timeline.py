#!/usr/bin/env python3
"""Estimate WHEN a roof was probably replaced from imagery vintages (no permit needed).

Compares same-type government vintages for a parcel (dak23 -> met25, both leaf-off ortho).
If the central-crop change score crosses the flag threshold, the replacement happened
between the two capture years; we record the midpoint year as an UNREVIEWED estimate.
Scoring hedges on it (roof_score_v2: 50/50 blend, flag PROBABLE_REROOF_IMAGERY_REVIEW).
Only a human review (evidence/data/roof_age_reviews.json) turns it into a full age reset.
A change can also be a new tarp, tree growth or snow: this is a flag, never a finding.
"""
import argparse, datetime as dt, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))
import roof_chip_features as cf  # noqa: E402

DATA = ROOT / "evidence" / "data"
LAYER_YEAR = {"dak23": 2023, "met25": 2025}      # same-type leaf-off vintages that may be compared


def estimate(pin, chip_dir, mask=None):
    d = pathlib.Path(chip_dir)
    have = sorted((y, l) for l, y in LAYER_YEAR.items() if (d / f"{pin}__{l}.jpg").exists())
    for (y0, l0), (y1, l1) in zip(have, have[1:]):
        score = cf.features_for(d / f"{pin}__{l1}.jpg", d / f"{pin}__{l0}.jpg", mask=mask)["change_score"]
        if score >= cf.CHANGE_FLAG:
            return {"between": [y0, y1], "estimated_year": (y0 + y1) // 2, "change_score": round(score, 4),
                    "reviewed": False, "basis": "IMAGERY_CHANGE_UNREVIEWED"}
    return None


def apply_reviews(records, reviews):
    """Human reviews (reviewer id + date required) override the estimate either way."""
    for r in reviews:
        if not (r.get("reviewer_id") and r.get("reviewed_at")):
            continue
        pin = r.get("county_pin")
        if r.get("status") == "REPLACED" and isinstance(r.get("year"), int):
            records[pin] = {"estimated_year": r["year"], "reviewed": True, "basis": "HUMAN_REVIEW",
                            "reviewer_id": r["reviewer_id"], "reviewed_at": r["reviewed_at"]}
        elif r.get("status") == "ORIGINAL":
            records.pop(pin, None)
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chip-dir", required=True)
    a = ap.parse_args()
    out = DATA / "reroof_timeline.json"
    try:
        records = json.loads(out.read_text(encoding="utf-8")).get("records", {})
    except (OSError, ValueError):
        records = {}
    pins = {p.name.split("__")[0] for p in pathlib.Path(a.chip_dir).glob("*__met25.jpg")}
    fp_path = DATA / "building_footprints.json"
    footprints = json.loads(fp_path.read_text())["records"] if fp_path.exists() else {}
    ledger = json.loads((DATA / "aerial_coverage_ledger.json").read_text())["records"] if footprints else {}
    for pin in sorted(pins):
        mask = None
        fp = footprints.get(pin, {})
        if fp.get("footprint_status") == "NEAREST_BUILDING_REVIEW_REQUIRED":
            from footprints import roof_mask
            mask = roof_mask(fp["footprint_geometry_4326"], ledger[pin]["bbox_4326"])
        est = estimate(pin, a.chip_dir, mask=mask)
        if est and not (records.get(pin) or {}).get("reviewed"):
            records[pin] = est
    try:
        reviews = json.loads((DATA / "roof_age_reviews.json").read_text(encoding="utf-8")).get("records", [])
    except (OSError, ValueError):
        reviews = []
    records = apply_reviews(records, reviews)
    out.write_text(json.dumps({"format": "AERO_REROOF_TIMELINE_V1_EXPERIMENTAL", "count": len(records),
                               "meaning": "Imagery-change estimate of replacement year. Unreviewed = hedge only.",
                               "records": records}, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"windows": len(records), "reviewed": sum(bool(r.get("reviewed")) for r in records.values())}))


if __name__ == "__main__":
    main()
