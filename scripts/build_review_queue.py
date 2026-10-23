#!/usr/bin/env python3
"""Human review queue: where one reviewer-minute buys the most.

queue_score = priority x (0.5 + (1 - confidence))
High priority AND thin evidence rise first (uncertainty sampling), so each
reviewed parcel teaches the system the most. The CSV is pre-filled with the
rights-checked remote source and image hash from the aerial ledger, and its
columns match what collector/roof_evidence_score.py reads from
evidence/data/roof_observations.json. A reviewer fills the blank columns;
nothing here is a finding.

View is AERIAL by default: an orthophoto cannot support a condition score
(roof_evidence_score.py enforces this). A CLOSE_RANGE/INSPECTION photo from an
authorized site visit or a consenting owner upload is what unlocks scoring.
"""
import argparse, csv, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))
DATA = ROOT / "evidence" / "data"
COLS = ["queue_rank", "county_pin", "parcel_objectid", "address", "tier", "prospecting_priority", "confidence",
        "flags", "source_type", "source_url", "image_sha256", "capture_date", "view",
        "roof_region_reviewed", "indicators", "lookalikes", "reviewer_id", "reviewed_at", "notes"]


def queue_score(r):
    return r["prospecting_priority"] * (0.5 + (1 - r["confidence"]))


def build(scores, ledger, discovery, k, url_fn):
    live = [r for r in scores["records"] if r.get("prospecting_priority") is not None and r.get("tier") in ("A", "B")]
    live.sort(key=lambda r: (-queue_score(r), r["county_pin"]))
    rows = []
    for i, r in enumerate(live[:k], 1):
        e = ledger.get(r["county_pin"]) or {}
        layer = e.get("preferred_layer")
        bbox = e.get("bbox_4326") or (discovery.get(r["county_pin"]) or {}).get("bbox_4326")
        rows.append({"queue_rank": i, "county_pin": r["county_pin"], "parcel_objectid": r.get("parcel_objectid"),
                     "address": r.get("address"), "tier": r["tier"], "prospecting_priority": r["prospecting_priority"],
                     "confidence": r["confidence"], "flags": ";".join(r.get("flags", [])),
                     "source_type": "MN_GOV" if layer else "",
                     "source_url": url_fn(bbox, layer) if layer and bbox else "",
                     "image_sha256": ((e.get("layers") or {}).get(layer) or {}).get("sha256", "") if layer else "",
                     "capture_date": "", "view": "AERIAL" if layer else "",
                     "roof_region_reviewed": "", "indicators": "", "lookalikes": "",
                     "reviewer_id": "", "reviewed_at": "", "notes": ""})
    return rows


def main():
    import collect_mngeo_aerial as mn
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--out", default=str(DATA / "review_queue.csv"))
    a = ap.parse_args()
    scores = json.loads((DATA / "roof_priority_v2.json").read_text(encoding="utf-8"))
    try:
        ledger = json.loads((DATA / "aerial_coverage_ledger.json").read_text(encoding="utf-8")).get("records", {})
    except (OSError, ValueError):
        ledger = {}
    disc = {r["county_pin"]: r for r in json.loads((DATA / "autonomous_residential_discovery.json").read_text(encoding="utf-8"))["records"]}
    rows = build(scores, ledger, disc, a.top, mn.url)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"queued": len(rows), "out": a.out}))


if __name__ == "__main__":
    main()
