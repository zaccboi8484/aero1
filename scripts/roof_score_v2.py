#!/usr/bin/env python3
"""Roof PROSPECTING PRIORITY v2 (expected-value ranking).

Replaces "count what evidence is missing" (54 of 60 parcels tied at 60) with a
transparent product of factors that can differ between parcels:

    ev = P(roof near end of life) x storm exposure x imagery flag
         x job-size factor x residential-class factor
    prospecting_priority = 100 * (1 - exp(-1.6 * ev))      # smooth, no ties from clipping

What it IS: an ordering of where to spend human review / outreach effort first.
What it is NOT: a damage score, a condition score, an insurance or hail finding.
The repo's gates stay intact: `roof_condition_score` is still produced only by
collector/roof_evidence_score.py after human-reviewed close-range evidence, and
only a verified final reroof permit can reset a roof's age.

All constants below are UNCALIBRATED engineering priors. collector/weak_label_model.py
exists to calibrate them once enough permit outcomes exist.
"""
import datetime as dt
import json
import math
import pathlib
import re
from pipeline_io import load_suppression, atomic_json

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "evidence" / "data"

CONST = {
    "roof_life_midpoint_years": 19.0,     # asphalt shingle: ~50% "due" at this age (prior)
    "roof_life_spread_years": 4.0,
    "age_unknown_prior": 0.35,
    "storm_lookback_years": 5,
    "hail_large_in": 1.75, "hail_mid_in": 1.0,
    "hail_boost": {"large": 0.35, "mid": 0.25, "any": 0.10}, "wind_boost_58mph": 0.12, "storm_cap": 0.6,
    "recency_weight": [(2, 1.0), (4, 0.7), (99, 0.4)],
    "chip_possible_change_mult": 0.75,    # a color/texture change often means a recent reroof
    "chip_possible_tarp_mult": 1.30,
    "value_ref_building_usd": 300000, "value_slope_per_usd": 1 / 1.5e6, "value_min": 0.8, "value_max": 1.3,
    "class_mult": {"SINGLE_FAMILY": 1.0, "DUPLEX": 0.8, "TOWNHOME": 0.45, "CONDO": 0.45, "MULTIFAMILY": 0.3,
                   "RESIDENTIAL_UNSPECIFIED": 1.0, "UNKNOWN": 1.0},
    "squash_k": 1.6,
    "tiers": (0.10, 0.40),                # top 10% = A, next 30% = B
}
EXCLUDED = {"NONRESIDENTIAL", "VACANT_OR_UNIMPROVED"}


import contextlib, copy


@contextlib.contextmanager
def const_override(**overrides):
    """Temporarily change CONST entries (used by score_interval.py for uncertainty sampling)."""
    saved = copy.deepcopy(CONST)
    try:
        CONST.update(overrides)
        yield
    finally:
        CONST.clear()
        CONST.update(saved)
CONF_WEIGHTS = {"year": .25, "class": .20, "storm": .15, "value": .10, "imagery": .20, "permit": .10}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _year(v):
    try:
        y = int(float(v))
        return y if 1800 <= y <= 2100 else None
    except (TypeError, ValueError):
        return None


def _date(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(s or ""))
    try:
        return dt.date(int(m[1]), int(m[2]), int(m[3])) if m else None
    except ValueError:
        return None


def storm_factor(events, ref_year, now_date):
    """Boost for NOAA-reported events in the parcel's ZCTA AFTER the roof's reference year.
    A reported point inside a ZCTA does not mean this roof was struck: the boost is modest and capped."""
    boost, used = 0.0, []
    for e in events or []:
        d = _date(e.get("date"))
        if not d or d > now_date:
            continue
        years_ago = (now_date - d).days / 365.25
        if years_ago > CONST["storm_lookback_years"] or (ref_year and d.year < ref_year):
            continue
        w = next(w for lim, w in CONST["recency_weight"] if years_ago <= lim)
        hail = e.get("hail_inches") or 0
        b = 0.0
        if hail >= CONST["hail_large_in"]:
            b += CONST["hail_boost"]["large"]
        elif hail >= CONST["hail_mid_in"]:
            b += CONST["hail_boost"]["mid"]
        elif hail > 0:
            b += CONST["hail_boost"]["any"]
        if (e.get("wind_mph") or 0) >= 58:
            b += CONST["wind_boost_58mph"]
        if b:
            boost += b * w
            used.append(e.get("event_id"))
    boost = min(boost, CONST["storm_cap"])
    return 1.0 + boost, used


def score_parcel(rec, ctx, now=None, use_permits=True):
    now = now or dt.datetime.now(dt.timezone.utc)
    pin = rec.get("county_pin")
    cls = rec.get("residential_class") or "UNKNOWN"
    base = {"county_pin": pin, "parcel_objectid": rec.get("parcel_objectid"), "address": rec.get("address"),
            "residential_class": cls, "not_a_damage_score": True, "condition_claim": "NONE"}
    if rec.get("non_residential_verified") or cls in EXCLUDED:
        return {**base, "status": "EXCLUDED_NOT_RESIDENTIAL_PROSPECT", "prospecting_priority": None}
    if pin in ctx.get("suppressed", ()):
        return {**base, "status": "SUPPRESSED_DO_NOT_CONTACT", "prospecting_priority": None}

    flags = []
    year_built = _year(rec.get("year_built")) or _year(ctx["year_built"].get(pin))
    reroof = ctx["reroof_year"].get(pin) if use_permits else None
    ref, basis = (reroof, "VERIFIED_REROOF_PERMIT") if reroof else (year_built, "YEAR_BUILT_PROXY")
    if ref is None:
        basis = "UNKNOWN"
        flags.append("ROOF_AGE_UNKNOWN")
    if basis == "YEAR_BUILT_PROXY":
        flags.append("ROOF_MAY_HAVE_BEEN_REPLACED_UNDETECTED")  # absent permit = unknown, never "original roof"
    age = now.year - ref if ref else None

    def p_of(a):
        return _clamp(1 / (1 + math.exp(-(a - CONST["roof_life_midpoint_years"]) / CONST["roof_life_spread_years"])), .03, .97)
    p_age = CONST["age_unknown_prior"] if age is None else p_of(age)
    window = (ctx.get("reroof_window") or {}).get(pin) if use_permits else None
    if window and not reroof:
        est = window["estimated_year"]
        if window.get("reviewed"):                       # a human confirmed the replacement: full reset
            ref, basis, age = est, "REVIEWED_IMAGERY_REROOF", now.year - est
            p_age = p_of(age)
        else:                                            # unreviewed imagery change: hedge, never reset
            p_age = 0.5 * p_of(now.year - est) + 0.5 * p_age
            flags.append("PROBABLE_REROOF_IMAGERY_REVIEW")

    z = str(rec.get("zip") or "")[:5]
    hail = ctx.get("hail") or {}
    if hail.get("covered"):                              # parcel-cell MRMS MESH over the whole lookback window
        storm_ok, storm_basis = True, "MRMS_MESH_PARCEL_CELL"
        storm_mult, storm_ids = storm_factor(hail["parcels"].get(pin, []), ref, now.date())
    else:
        storm_ok, storm_basis = z in ctx["storm_zips"], "NOAA_ZCTA_REPORT_POINTS"
        storm_mult, storm_ids = storm_factor(ctx["storms"].get(z), ref, now.date()) if storm_ok else (1.0, [])
        if not storm_ok:
            flags.append("STORM_DATA_NOT_COVERING_THIS_ZIP")

    chip = ctx["chips"].get(pin) or {}
    imagery_mult = 1.0
    if chip and not chip.get("error"):
        if chip.get("possible_roof_change"):
            imagery_mult *= CONST["chip_possible_change_mult"]
            flags.append("POSSIBLE_ROOF_CHANGE_REVIEW")
        if chip.get("possible_tarp"):
            imagery_mult *= CONST["chip_possible_tarp_mult"]
            flags.append("POSSIBLE_TARP_REVIEW")

    bv = ctx["building_value"].get(pin)
    value_factor = (1.0 if bv is None else
                    _clamp(CONST["value_min"] + (bv - CONST["value_ref_building_usd"]) * CONST["value_slope_per_usd"],
                           CONST["value_min"], CONST["value_max"]))
    if bv is None:
        flags.append("VALUATION_UNAVAILABLE")

    size_basis = "BUILDING_VALUATION" if bv is not None else "NEUTRAL_NO_SIZE_DATA"
    footprint = ctx.get("footprints", {}).get(pin, {})
    area = footprint.get("roof_area_m2_est")
    if (footprint.get("footprint_status") == "NEAREST_BUILDING_REVIEW_REQUIRED"
            and isinstance(area, (int, float)) and math.isfinite(area) and area > 0):
        value_factor = _clamp(0.8 + (area - 200) / 600, 0.8, 1.3)
        size_basis = "BUILDING_FOOTPRINT_ASSUMED_PITCH"
        flags.extend(["ROOF_AREA_ASSUMED_PITCH", "FOOTPRINT_MATCH_REVIEW_REQUIRED"])

    type_mult = CONST["class_mult"].get(cls, 1.0)
    verified = bool(rec.get("single_family_verified"))
    like = rec.get("residential_likelihood")
    like = 0.5 if like is None else like
    class_mult = type_mult * (1.0 if verified else like)
    if not verified:
        flags.append("RESIDENTIAL_CLASS_NOT_VERIFIED")

    cohort_mult = (ctx.get("cohort_mult") or {}).get(pin, 1.0)
    if cohort_mult != 1.0:
        flags.append("COHORT_REVIEW_ADJUSTED")
    ev = p_age * storm_mult * imagery_mult * value_factor * class_mult * cohort_mult
    priority = round(100 * (1 - math.exp(-CONST["squash_k"] * ev)), 1)
    have = {"year": ref is not None, "class": verified, "storm": storm_ok, "value": bv is not None,
            "imagery": (ctx["aerial"].get(pin) or {}).get("status") == "REMOTE_IMAGE_VERIFIED",
            "permit": bool(reroof)}
    confidence = round(sum(w for k, w in CONF_WEIGHTS.items() if have[k]), 2)
    return {**base, "status": "PROSPECTING_PRIORITY_V2", "prospecting_priority": priority,
            "expected_value": round(ev, 4), "confidence": confidence, "flags": flags,
            "factors": {"roof_age_years": age, "age_basis": basis, "p_age": round(p_age, 3),
                        "storm_mult": round(storm_mult, 3), "storm_basis": storm_basis, "storm_event_ids": storm_ids,
                        "cohort_mult": round(cohort_mult, 3),
                        "imagery_mult": round(imagery_mult, 3), "value_factor": round(value_factor, 3),
                        "class_mult": round(class_mult, 3), "size_basis": size_basis}}


def assign_tiers(results):
    live = sorted((r for r in results if r.get("prospecting_priority") is not None),
                  key=lambda r: (-r["prospecting_priority"], -r["confidence"], r["county_pin"]))
    n = len(live)
    a_cut, b_cut = math.ceil(n * CONST["tiers"][0]), math.ceil(n * CONST["tiers"][1])
    for i, r in enumerate(live):
        r["rank"] = i + 1
        r["tier"] = "A" if i < a_cut else "B" if i < b_cut else "C"
    return results


def _read(name, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _hail_ctx(now=None):
    """MRMS hail counts as coverage only if candidate hail days are processed across the whole lookback
    window and the store is current."""
    h = _read("hail_exposure.json", {})
    if not h.get("coverage_from") or not h.get("coverage_through"):
        return {"covered": False, "parcels": {}}
    now = now or dt.datetime.now(dt.timezone.utc)
    start = now.date() - dt.timedelta(days=int(365.25 * CONST["storm_lookback_years"]))
    ok = (dt.date.fromisoformat(h["coverage_from"]) <= start + dt.timedelta(days=30) and
          dt.date.fromisoformat(h["coverage_through"]) >= now.date() - dt.timedelta(days=14))
    return {"covered": ok, "parcels": h.get("parcels", {})}


def build_context(data_dir=None, now=None):
    global DATA
    if data_dir:
        DATA = pathlib.Path(data_dir)
    val = _read("live_property_enrichment.json", {}).get("records", [])
    storm = _read("zcta_storm_index.json", {})
    storms = {x["zcta"]: x.get("reports", []) for x in storm.get("events_by_zip", [])}
    reroof = {}
    for r in _read("roof_permit_backfill_2025.json", {}).get("records", []):
        if r.get("recent_roof_verified"):
            ys = [_date(p.get("final_date") or p.get("issued_date") or p.get("date") or "") for p in r.get("matched_roof_permits", [])
                  if isinstance(p, dict)]
            ys = [d.year for d in ys if d]
            y = max(ys) if ys else _year(r.get("last_year"))
            if y:
                reroof[r["county_pin"]] = y
    return {"building_value": {r["county_pin"]: (r.get("valuation") or {}).get("building_value_usd") for r in val
                               if (r.get("valuation") or {}).get("gatekeeper") == "SOURCE_RECORDED"},
            "year_built": {r["county_pin"]: (r.get("valuation") or {}).get("year_built") for r in val},
            "storms": storms,
            "storm_zips": {x["zcta"] for x in storm.get("zip_areas", [])},
            "reroof_year": reroof,
            "aerial": _read("aerial_coverage_ledger.json", {}).get("records", {}),
            "chips": _read("roof_chip_features.json", {}).get("records", {}),
            "hail": _hail_ctx(now),
            "reroof_window": _read("reroof_timeline.json", {}).get("records", {}),
            "suppressed": load_suppression(DATA / "outreach_suppression.json"),
            "cohort_mult": _read("cohort_multipliers.json", {}).get("records", {}),
            "footprints": _read("building_footprints.json", {}).get("records", {})}


def run(data_dir=None, now=None):
    ctx = build_context(data_dir, now)
    recs = _read("autonomous_residential_discovery.json", {}).get("records", [])
    results = assign_tiers([score_parcel(r, ctx, now) for r in recs])
    live = [r for r in results if r.get("prospecting_priority") is not None]
    body = {"format": "AERO_ROOF_PROSPECTING_PRIORITY_V2", "generated_at_utc": (now or dt.datetime.now(dt.timezone.utc)).isoformat(),
            "method": "HEURISTIC_UNCALIBRATED", "constants": CONST,
            "meaning": "Where to spend review/outreach effort first. NOT roof damage, condition, hail attribution or a replacement finding.",
            "count": len(results), "scored": len(live),
            "tiers": {t: sum(r["tier"] == t for r in live) for t in "ABC"},
            "excluded": len(results) - len(live), "records": results}
    out = DATA / "roof_priority_v2.json"
    try:  # unchanged results -> leave the file alone so the 15-minute cron does not create empty-diff commits
        old = json.loads(out.read_text(encoding="utf-8"))
        if {k: v for k, v in old.items() if k != "generated_at_utc"} == {k: v for k, v in body.items() if k != "generated_at_utc"}:
            return body
    except (OSError, ValueError):
        pass
    atomic_json(out, body)
    return body


if __name__ == "__main__":
    b = run()
    print(json.dumps({k: b[k] for k in ("count", "scored", "tiers", "excluded")}))
