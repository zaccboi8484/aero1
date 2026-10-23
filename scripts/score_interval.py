#!/usr/bin/env python3
"""Rank on a pessimistic bound, not a point estimate.

Our constants are priors. We resample the uncertain ones and score each parcel N times; the 20th
percentile (p20) is the ranking key, so a parcel that is high ONLY under optimistic assumptions
drops. Output: evidence/data/roof_priority_interval.json with p20/p50/p80 and a robust rank.
"""
import json, pathlib, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import roof_score_v2 as v2  # noqa: E402


def draw(rng):
    return {"roof_life_midpoint_years": float(rng.normal(19, 2.5)),
            "roof_life_spread_years": float(rng.uniform(3.0, 5.5)),
            "age_unknown_prior": float(rng.uniform(0.25, 0.45)),
            "hail_boost": {k: v * float(rng.uniform(0.6, 1.4)) for k, v in v2.CONST["hail_boost"].items()}}


def intervals(recs, ctx, now, n=200, seed=7, only=None):
    rng = np.random.default_rng(seed)
    samples = [draw(rng) for _ in range(n)]
    out = {}
    pool = [r for r in recs if only is None or r["county_pin"] in only]
    mat = {}
    for s in samples:
        with v2.const_override(**s):
            for r in pool:
                p = v2.score_parcel(r, ctx, now)["prospecting_priority"]
                if p is not None:
                    mat.setdefault(r["county_pin"], []).append(p)
    for pin, v in mat.items():
        out[pin] = {"p20": round(float(np.percentile(v, 20)), 1), "p50": round(float(np.percentile(v, 50)), 1),
                    "p80": round(float(np.percentile(v, 80)), 1)}
    return out


def main():
    ctx = v2.build_context()
    scores = json.loads((v2.DATA / "roof_priority_v2.json").read_text(encoding="utf-8"))
    recs = v2._read("autonomous_residential_discovery.json", {}).get("records", [])
    top = {r["county_pin"] for r in scores["records"] if r.get("tier") in ("A", "B")}   # tier C never reaches review
    iv = intervals(recs, ctx, None, only=top)
    ranked = sorted(iv.items(), key=lambda kv: (-kv[1]["p20"], kv[0]))
    body = {"format": "AERO_PRIORITY_INTERVAL_V1", "samples": 200, "rank_key": "p20",
            "records": {pin: {**v, "robust_rank": i + 1} for i, (pin, v) in enumerate(ranked)}}
    (v2.DATA / "roof_priority_interval.json").write_text(json.dumps(body, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"parcels": len(ranked)}))


if __name__ == "__main__":
    main()
