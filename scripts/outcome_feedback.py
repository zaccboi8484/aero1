#!/usr/bin/env python3
"""Close the loop: did higher tiers actually book more work?

WHERE OUTCOMES COME FROM (they are YOUR data, nobody publishes them):
  * Your CRM / dialer / field app exports a CSV, OR
  * the field app writes rows to the Supabase table outreach_outcomes (migration 008).
  Columns: export_id, county_pin, tier_at_export, priority_at_export, outcome, outcome_at.
  The tier/priority at export time come from scripts/export_outreach_list.py, so later re-scoring
  cannot rewrite history. No names, phones or emails are used or stored here.

WHAT IT DOES
  1. Beta(1,1) posterior booking rate per tier with a 90% interval.
  2. Monotonic check: tier A >= B >= C once each has >= MIN_N attempts. A violation fails the run.
  3. Priority-decile table (empirical rate by decile) for calibration.
  4. Writes evidence/data/outreach_suppression.json (pins only) from DO_NOT_CONTACT outcomes;
     roof_score_v2 then excludes them.
"""
import argparse, csv, json, os, pathlib, sys, urllib.request
from scipy.stats import beta as beta_dist
from pipeline_io import load_suppression, atomic_json

DATA = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "data"
POSITIVE = {"APPOINTMENT", "BOOKED"}
ATTEMPTED_EXCLUDE = {"NOT_ATTEMPTED"}
MIN_N = 100


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_supabase(url=None, key=None, table="outreach_outcomes"):
    url, key = url or os.environ["SUPABASE_URL"], key or os.environ["SUPABASE_SERVICE_KEY"]
    req = urllib.request.Request(f"{url}/rest/v1/{table}?select=export_id,county_pin,tier_at_export,priority_at_export,outcome,outcome_at",
                                 headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def analyze(rows):
    att = [r for r in rows if r.get("outcome") not in ATTEMPTED_EXCLUDE and r.get("tier_at_export") in ("A", "B", "C")]
    tiers = {}
    for t in "ABC":
        n = [r for r in att if r["tier_at_export"] == t]
        pos = sum(r["outcome"] in POSITIVE for r in n)
        a, b = 1 + pos, 1 + len(n) - pos
        lo, hi = beta_dist.ppf([.05, .95], a, b)
        tiers[t] = {"attempts": len(n), "positive": pos, "rate": round(a / (a + b), 4),
                    "ci90": [round(float(lo), 4), round(float(hi), 4)]}
    enough = all(tiers[t]["attempts"] >= MIN_N for t in "ABC")
    mono = (tiers["A"]["rate"] >= tiers["B"]["rate"] >= tiers["C"]["rate"]) if enough else None
    dec = {}
    for r in att:
        try:
            d = min(9, int(float(r["priority_at_export"]) // 10))
        except (TypeError, ValueError):
            continue
        x = dec.setdefault(d, [0, 0])
        x[0] += 1
        x[1] += r["outcome"] in POSITIVE
    return {"tiers": tiers, "monotonic_ok": mono,
            "status": "INSUFFICIENT_DATA" if not enough else ("OK" if mono else "TIERS_NOT_MONOTONIC_REVIEW_WEIGHTS"),
            "priority_decile_rates": {f"{k*10}-{k*10+9}": {"n": v[0], "rate": round(v[1] / v[0], 4)} for k, v in sorted(dec.items())},
            "suppress_pins": sorted({r["county_pin"] for r in rows if r.get("outcome") == "DO_NOT_CONTACT"})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--supabase", action="store_true")
    a = ap.parse_args()
    rows = read_supabase() if a.supabase else read_csv(a.csv)
    rep = analyze(rows)
    sup = rep.pop("suppress_pins")
    prev = load_suppression(DATA / "outreach_suppression.json")
    atomic_json(DATA / "outreach_suppression.json",
                {"pins": sorted(prev | set(sup)), "note": "Never removed automatically."})
    atomic_json(DATA / "outcome_feedback_report.json", rep)
    print(json.dumps({"status": rep["status"], "tiers": rep["tiers"], "suppressed": len(prev | set(sup))}))
    return 1 if rep["status"] == "TIERS_NOT_MONOTONIC_REVIEW_WEIGHTS" else 0


if __name__ == "__main__":
    sys.exit(main())
