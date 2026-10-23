#!/usr/bin/env python3
"""Cohort adjustment: homes built in the same few years, same ZIP, tend to share a roof history.

Reviewed roof-age outcomes (evidence/data/roof_age_reviews.json: REPLACED or ORIGINAL, with reviewer id
and date) of a pin's cohort nudge that pin's priority. Needs >= MIN_PEERS reviewed peers; otherwise 1.0.
The multiplier is small by design (0.85 .. 1.15) because a cohort is a hint, not evidence about one roof.
"""
import json, pathlib
from collections import defaultdict

DATA = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "data"
MIN_PEERS = 5


def key(r):
    try:
        return (str(r.get("zip") or "")[:5], int(r["year_built"]) // 3)
    except (KeyError, TypeError, ValueError):
        return None


def multipliers(recs, reviews):
    ok = {x["county_pin"]: x["status"] for x in reviews
          if x.get("reviewer_id") and x.get("reviewed_at") and x.get("status") in ("REPLACED", "ORIGINAL")}
    groups = defaultdict(list)
    for r in recs:
        k = key(r)
        if k and k[1] > 600:
            groups[k].append(r["county_pin"])
    out = {}
    for pins in groups.values():
        peers = [ok[p] for p in pins if p in ok]
        if len(peers) < MIN_PEERS:
            continue
        replaced = sum(s == "REPLACED" for s in peers) / len(peers)
        m = 1.15 if replaced < 0.2 else 0.85 if replaced > 0.6 else 1.0
        if m != 1.0:
            out.update({p: m for p in pins if p not in ok})   # reviewed pins keep their own evidence
    return out


def main():
    recs = json.loads((DATA / "autonomous_residential_discovery.json").read_text(encoding="utf-8"))["records"]
    try:
        reviews = json.loads((DATA / "roof_age_reviews.json").read_text(encoding="utf-8")).get("records", [])
    except (OSError, ValueError):
        reviews = []
    m = multipliers(recs, reviews)
    (DATA / "cohort_multipliers.json").write_text(json.dumps({"format": "AERO_COHORT_V1", "min_peers": MIN_PEERS,
                                                              "records": m}, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"adjusted": len(m)}))


if __name__ == "__main__":
    main()
