#!/usr/bin/env python3
"""Export the outreach list WITH the tier/priority it had at export time (needed to score outcomes later).

Writes evidence/outreach/<export_id>.csv (git-ignored: it is a work list, not evidence).
Suppressed (do-not-contact) pins never appear. Register export_id + sha256 in outreach_exports,
and have the field/CRM tool write one outreach_outcomes row per pin (pin + outcome only, no PII).
"""
import argparse, csv, datetime as dt, hashlib, json, pathlib, uuid
from pipeline_io import load_suppression

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "evidence" / "data"


def select(scores, suppressed, tiers, top):
    if top < 1 or not tiers or not tiers <= {"A", "B", "C"}:
        raise ValueError("top must be positive and tiers must contain only A, B, C")
    rows = [r for r in scores["records"] if r.get("tier") in tiers and r["county_pin"] not in suppressed]
    rows.sort(key=lambda r: (r["rank"]))
    return rows[:top]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="A")
    ap.add_argument("--top", type=int, default=200)
    a = ap.parse_args()
    scores = json.loads((DATA / "roof_priority_v2.json").read_text(encoding="utf-8"))
    sup = load_suppression(DATA / "outreach_suppression.json")
    rows = select(scores, sup, set(a.tiers), a.top)
    export_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    out = ROOT / "evidence" / "outreach" / f"{export_id}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["export_id", "county_pin", "address", "tier_at_export", "priority_at_export", "flags"])
        for r in rows:
            w.writerow([export_id, r["county_pin"], r.get("address"), r["tier"], r["prospecting_priority"], ";".join(r.get("flags", []))])
    print(json.dumps({"export_id": export_id, "rows": len(rows), "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
