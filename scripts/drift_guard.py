#!/usr/bin/env python3
"""Fail the cron BEFORE bad data is committed. Compare this run's metrics to the last good baseline."""
import json, pathlib, statistics, sys

DATA = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "data"
LIMITS = {"unknown_class_share_up": 0.10, "imagery_error_rate_max": 0.30, "median_priority_shift": 8.0}


def metrics(discovery, ledger, scores):
    recs = discovery.get("records", [])
    unk = sum((r.get("residential_class") or "UNCLASSIFIED") in ("UNKNOWN", "UNCLASSIFIED") for r in recs)
    led = list(ledger.get("records", {}).values())
    bad = sum(e.get("status") != "REMOTE_IMAGE_VERIFIED" for e in led)
    pr = [r["prospecting_priority"] for r in scores.get("records", []) if r.get("prospecting_priority") is not None]
    return {"parcels": len(recs), "unknown_class_share": round(unk / len(recs), 4) if recs else 0.0,
            "imagery_error_rate": round(bad / len(led), 4) if led else 0.0,
            "median_priority": round(statistics.median(pr), 2) if pr else None,
            "tier_a_count": sum(r.get("tier") == "A" for r in scores.get("records", []))}


def check(prev, now):
    problems = []
    if prev and now["parcels"] < prev["parcels"]:
        problems.append("parcel count went DOWN (records lost)")
    if prev and now["unknown_class_share"] > prev["unknown_class_share"] + LIMITS["unknown_class_share_up"]:
        problems.append("classification regressed")
    if now["imagery_error_rate"] > LIMITS["imagery_error_rate_max"]:
        problems.append("imagery source degraded")
    if prev and prev["median_priority"] is not None and now["median_priority"] is not None and \
            abs(now["median_priority"] - prev["median_priority"]) > LIMITS["median_priority_shift"]:
        problems.append("score distribution shifted")
    if now["parcels"] and now["tier_a_count"] == 0:
        problems.append("no tier A parcels")
    return problems


def main():
    def rd(n):
        try:
            return json.loads((DATA / n).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    now = metrics(rd("autonomous_residential_discovery.json"), rd("aerial_coverage_ledger.json"), rd("roof_priority_v2.json"))
    prev = rd("drift_baseline.json") or None
    problems = check(prev, now)
    print(json.dumps({"metrics": now, "problems": problems}))
    if problems:
        return 1
    (DATA / "drift_baseline.json").write_text(json.dumps(now, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
