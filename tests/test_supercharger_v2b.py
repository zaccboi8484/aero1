"""Offline tests for hail swath, reroof timeline, cohorts, outcomes, storm trigger, intervals, provenance, drift.
Synthetic inputs are test-only and are not evidence."""
import datetime as dt, json, pathlib, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
for sub in ("collector", "scripts"):
    sys.path.insert(0, str(ROOT / sub))
import numpy as np
from PIL import Image
import hail_swath as hs, reroof_timeline as rt, cohorts as co, outcome_feedback as of
import storm_trigger as st, score_interval as si, provenance_chain as pc, drift_guard as dg
import roof_score_v2 as v2, export_outreach_list as eo

NOW = dt.datetime(2026, 10, 23, tzinfo=dt.timezone.utc)
CTX = {"building_value": {}, "year_built": {}, "storms": {}, "storm_zips": set(), "reroof_year": {}, "aerial": {}, "chips": {}}
def ctx(**kw): return {**CTX, **kw}
def rec(pin="1", yb=1996, **kw):
    return {"county_pin": pin, "year_built": yb, "residential_class": "SINGLE_FAMILY", "single_family_verified": True,
            "residential_likelihood": .97, "zip": "55123", **kw}

class Hail(unittest.TestCase):
    def test_pick_key_nearest_noon(self):
        keys = [f"CONUS/MESH_Max_1440min_00.50/20260502/MRMS_MESH_Max_1440min_00.50_20260502-{t}.grib2.gz" for t in ("003000", "115800", "235800")]
        self.assertIn("115800", hs.pick_key(keys))
        self.assertIsNone(hs.pick_key(["junk.txt"]))
    def test_sample_points_units_nodata_and_outside(self):
        lats = np.arange(45.0, 44.0, -0.01); lons = np.arange(-94.0, -93.0, 0.01)
        g = np.full((len(lats), len(lons)), -3.0, dtype=np.float32)
        i, j = int(np.abs(lats - 44.8).argmin()), int(np.abs(lons + 93.17).argmin())
        g[i, j] = 50.8; g[i + 1, j] = 76.2
        out = hs.sample_points(g, lats, lons, [("in", -93.17, 44.8), ("nodata", -93.5, 44.5), ("outside", -80.0, 30.0)])
        self.assertEqual(out["in"], (2.0, 3.0)); self.assertEqual(out["nodata"], (0.0, 0.0)); self.assertNotIn("outside", out)
    def test_merge_day_skips_trace_and_marks_processed(self):
        s = {"parcels": {}, "processed_days": {}}
        hs.merge_day(s, dt.date(2026, 5, 1), {"a": (1.5, 1.75), "b": (0.0, 0.1)}, "k")
        self.assertEqual(list(s["parcels"]), ["a"]); self.assertIn("2026-05-01", s["processed_days"])
    def test_candidate_days_hail_only(self):
        d = {"events": [{"kind": "HAIL", "sort_key": "2026-06-19T17:00:00"}, {"kind": "TSTM WIND", "sort_key": "2026-06-20T10:00:00"}]}
        self.assertEqual(hs.candidate_days(d), [dt.date(2026, 6, 19)])
    def test_run_end_to_end_with_fakes_and_coverage(self):
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            (d / "noaa_storm_events_scoped.json").write_text(json.dumps({"events": [{"kind": "HAIL", "sort_key": "2026-06-19T17:00:00"}]}))
            (d / "autonomous_residential_discovery.json").write_text(json.dumps({"records": [{"county_pin": "p", "center_lat": 44.8, "center_lon": -93.17}]}))
            hs.DATA, hs.OUT = d, d / "hail_exposure.json"
            lats = np.arange(45.0, 44.0, -0.01); lons = np.arange(-94.0, -93.0, 0.01)
            g = np.zeros((len(lats), len(lons)), dtype=np.float32); g[int(np.abs(lats - 44.8).argmin()), int(np.abs(lons + 93.17).argmin())] = 44.45
            r = hs.run(5, 5, grid_fetch=lambda k: (g, lats, lons), lister=lambda day: [f"x_{day:%Y%m%d}-120000.grib2.gz"], today=dt.date(2026, 10, 23))
            self.assertEqual(r["days_processed_this_run"], 1)
            s = json.loads(hs.OUT.read_text())
            self.assertEqual(s["parcels"]["p"][0]["hail_inches"], 1.75); self.assertEqual(s["pending_candidate_days"], 0)
            self.assertEqual(hs.run(5, 5, grid_fetch=lambda k: 1 / 0, lister=lambda day: [], today=dt.date(2026, 10, 23))["days_processed_this_run"], 0)

class HailScoring(unittest.TestCase):
    def test_parcel_cell_hail_used_when_covered_and_raises_priority(self):
        h = {"covered": True, "parcels": {"1": [{"event_id": "e", "date": "2026-05-01", "hail_inches": 2.0}]}}
        a = v2.score_parcel(rec(), ctx(hail=h), NOW); b = v2.score_parcel(rec(), ctx(hail={"covered": True, "parcels": {}}), NOW)
        self.assertGreater(a["prospecting_priority"], b["prospecting_priority"]); self.assertEqual(a["factors"]["storm_basis"], "MRMS_MESH_PARCEL_CELL")
        self.assertNotIn("STORM_DATA_NOT_COVERING_THIS_ZIP", a["flags"])
    def test_uncovered_hail_store_falls_back_to_zip_logic(self):
        x = v2.score_parcel(rec(), ctx(hail={"covered": False, "parcels": {}}), NOW)
        self.assertEqual(x["factors"]["storm_basis"], "NOAA_ZCTA_REPORT_POINTS"); self.assertIn("STORM_DATA_NOT_COVERING_THIS_ZIP", x["flags"])
    def test_coverage_requires_span_and_freshness(self):
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t); old = v2.DATA; v2.DATA = d
            try:
                (d / "hail_exposure.json").write_text(json.dumps({"coverage_from": "2021-10-01", "coverage_through": "2026-10-20", "parcels": {}}))
                self.assertTrue(v2._hail_ctx(NOW)["covered"])
                (d / "hail_exposure.json").write_text(json.dumps({"coverage_from": "2025-10-01", "coverage_through": "2026-10-20", "parcels": {}}))
                self.assertFalse(v2._hail_ctx(NOW)["covered"])
                (d / "hail_exposure.json").write_text(json.dumps({"coverage_from": "2021-10-01", "coverage_through": "2026-08-01", "parcels": {}}))
                self.assertFalse(v2._hail_ctx(NOW)["covered"])
            finally: v2.DATA = old

class Reroof(unittest.TestCase):
    def mk(self, d, name, color, noise, seed):
        a = np.full((233, 300, 3), color, dtype=np.float32) + np.random.default_rng(seed).normal(0, noise, (233, 300, 3))
        Image.fromarray(np.clip(a, 0, 255).astype("uint8")).save(d / name)
    def test_estimate_midpoint_and_no_change(self):
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            self.mk(d, "p__dak23.jpg", (110, 105, 100), 12, 1); self.mk(d, "p__met25.jpg", (110, 105, 100), 40, 9)
            self.mk(d, "q__dak23.jpg", (110, 105, 100), 12, 1); self.mk(d, "q__met25.jpg", (125, 120, 116), 12, 1)
            e = rt.estimate("p", d); self.assertEqual((e["estimated_year"], e["reviewed"]), (2024, False))
            self.assertIsNone(rt.estimate("q", d))
    def test_reviews_need_reviewer_and_override(self):
        recs = {"p": {"estimated_year": 2024, "reviewed": False}}
        rt.apply_reviews(recs, [{"county_pin": "p", "status": "REPLACED", "year": 2022}])           # no reviewer: ignored
        self.assertEqual(recs["p"]["estimated_year"], 2024)
        rt.apply_reviews(recs, [{"county_pin": "p", "status": "REPLACED", "year": 2022, "reviewer_id": "r1", "reviewed_at": "2026-10-01T00:00:00+00:00"}])
        self.assertTrue(recs["p"]["reviewed"]); self.assertEqual(recs["p"]["estimated_year"], 2022)
        rt.apply_reviews(recs, [{"county_pin": "p", "status": "ORIGINAL", "reviewer_id": "r1", "reviewed_at": "2026-10-02T00:00:00+00:00"}])
        self.assertNotIn("p", recs)
    def test_unreviewed_window_hedges_reviewed_resets(self):
        base = v2.score_parcel(rec(yb=1996), CTX, NOW)["prospecting_priority"]
        hedge = v2.score_parcel(rec(yb=1996), ctx(reroof_window={"1": {"estimated_year": 2024, "reviewed": False}}), NOW)
        reset = v2.score_parcel(rec(yb=1996), ctx(reroof_window={"1": {"estimated_year": 2024, "reviewed": True}}), NOW)
        self.assertLess(hedge["prospecting_priority"], base); self.assertGreater(hedge["prospecting_priority"], reset["prospecting_priority"])
        self.assertIn("PROBABLE_REROOF_IMAGERY_REVIEW", hedge["flags"]); self.assertEqual(reset["factors"]["age_basis"], "REVIEWED_IMAGERY_REROOF")

class Cohorts(unittest.TestCase):
    def test_multiplier_needs_reviewed_peers(self):
        recs = [rec(str(i), 1996) for i in range(10)]
        rv = lambda n, s: [{"county_pin": str(i), "status": s, "reviewer_id": "r", "reviewed_at": "x"} for i in range(n)]
        self.assertEqual(co.multipliers(recs, rv(4, "ORIGINAL")), {})
        m = co.multipliers(recs, rv(6, "ORIGINAL"))
        self.assertEqual(set(m), {"6", "7", "8", "9"}); self.assertEqual(set(m.values()), {1.15})
        self.assertEqual(set(co.multipliers(recs, rv(6, "REPLACED")).values()), {0.85})
    def test_unreviewed_reviews_ignored(self):
        recs = [rec(str(i), 1996) for i in range(10)]
        self.assertEqual(co.multipliers(recs, [{"county_pin": str(i), "status": "ORIGINAL"} for i in range(8)]), {})
    def test_cohort_flagged_in_score(self):
        self.assertIn("COHORT_REVIEW_ADJUSTED", v2.score_parcel(rec(), ctx(cohort_mult={"1": 1.15}), NOW)["flags"])

class Outcomes(unittest.TestCase):
    def rows(self, rates, n=120):
        out = []
        for t, r in zip("ABC", rates):
            for i in range(n):
                out.append({"tier_at_export": t, "priority_at_export": {"A": 55, "B": 35, "C": 15}[t], "county_pin": f"{t}{i}",
                            "outcome": "BOOKED" if i < int(n * r) else "NO_CONTACT"})
        return out
    def test_monotonic_ok_and_intervals(self):
        r = of.analyze(self.rows((.2, .1, .05))); self.assertEqual(r["status"], "OK")
        self.assertLess(r["tiers"]["A"]["ci90"][0], r["tiers"]["A"]["rate"] < r["tiers"]["A"]["ci90"][1] or 1)
    def test_non_monotonic_fails(self):
        self.assertEqual(of.analyze(self.rows((.05, .1, .2)))["status"], "TIERS_NOT_MONOTONIC_REVIEW_WEIGHTS")
    def test_thin_data_is_insufficient_not_ok(self):
        self.assertEqual(of.analyze(self.rows((.2, .1, .05), n=20))["status"], "INSUFFICIENT_DATA")
    def test_do_not_contact_collected_and_excluded_from_scoring(self):
        r = of.analyze([{"tier_at_export": "A", "priority_at_export": 50, "county_pin": "z", "outcome": "DO_NOT_CONTACT"}])
        self.assertEqual(r["suppress_pins"], ["z"])
        self.assertEqual(v2.score_parcel(rec("z"), ctx(suppressed={"z"}), NOW)["status"], "SUPPRESSED_DO_NOT_CONTACT")
    def test_export_excludes_suppressed_and_other_tiers(self):
        sc = {"records": [{"county_pin": "a", "tier": "A", "rank": 1}, {"county_pin": "b", "tier": "A", "rank": 2}, {"county_pin": "c", "tier": "B", "rank": 3}]}
        self.assertEqual([r["county_pin"] for r in eo.select(sc, {"a"}, {"A"}, 10)], ["b"])

class Trigger(unittest.TestCase):
    STORE = {"parcels": {"a": [{"event_id": "MRMS-20260501", "hail_inches": 2.0}], "b": [{"event_id": "MRMS-20260501", "hail_inches": 0.5}],
                         "c": [{"event_id": "MRMS-20260501", "hail_inches": 1.5}]}}
    def test_new_events_once(self):
        self.assertEqual(st.new_events(self.STORE, []), ["MRMS-20260501"]); self.assertEqual(st.new_events(self.STORE, ["MRMS-20260501"]), [])
    def test_alerts_only_hit_ab_sorted(self):
        sc = {"records": [{"county_pin": "a", "tier": "A", "prospecting_priority": 60, "address": "x"},
                          {"county_pin": "b", "tier": "A", "prospecting_priority": 70}, {"county_pin": "c", "tier": "C", "prospecting_priority": 90}]}
        self.assertEqual([r["county_pin"] for r in st.alerts(self.STORE, sc, {"MRMS-20260501"})], ["a"])

class Intervals(unittest.TestCase):
    def test_override_restores_const(self):
        before = json.dumps(v2.CONST, sort_keys=True)
        with v2.const_override(roof_life_midpoint_years=5.0): self.assertEqual(v2.CONST["roof_life_midpoint_years"], 5.0)
        self.assertEqual(json.dumps(v2.CONST, sort_keys=True), before)
    def test_ordered_percentiles_deterministic(self):
        recs = [rec(str(y), y) for y in (1980, 1996, 2010)]
        a = si.intervals(recs, CTX, NOW, n=60); b = si.intervals(recs, CTX, NOW, n=60)
        self.assertEqual(a, b)
        for v in a.values(): self.assertLessEqual(v["p20"], v["p50"]); self.assertLessEqual(v["p50"], v["p80"])
        self.assertGreater(a["1980"]["p20"], a["2010"]["p20"])

class Provenance(unittest.TestCase):
    def test_chain_append_noop_and_tamper(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / "c.jsonl"
            pc.append(p, {"f": "1"}, "t1"); self.assertIsNone(pc.append(p, {"f": "1"}, "t2")); pc.append(p, {"f": "2"}, "t3")
            self.assertTrue(pc.verify(p)["ok"])
            lines = p.read_text().splitlines(); first = json.loads(lines[0]); first["files"] = {"f": "X"}
            p.write_text("\n".join([json.dumps(first, sort_keys=True)] + lines[1:]) + "\n")
            self.assertEqual(pc.verify(p), {"ok": False, "broken_at": 0})

class Drift(unittest.TestCase):
    NOW = {"parcels": 100, "unknown_class_share": .2, "imagery_error_rate": .05, "median_priority": 30, "tier_a_count": 10}
    def test_ok_and_each_failure(self):
        self.assertEqual(dg.check(self.NOW, self.NOW), [])
        self.assertIn("classification regressed", dg.check(self.NOW, {**self.NOW, "unknown_class_share": .5}))
        self.assertIn("imagery source degraded", dg.check(self.NOW, {**self.NOW, "imagery_error_rate": .4}))
        self.assertIn("score distribution shifted", dg.check(self.NOW, {**self.NOW, "median_priority": 45}))
        self.assertIn("parcel count went DOWN (records lost)", dg.check(self.NOW, {**self.NOW, "parcels": 90}))
        self.assertIn("no tier A parcels", dg.check(None, {**self.NOW, "tier_a_count": 0}))
if __name__ == "__main__": unittest.main()
