"""Offline tests for classification, scoring v2, aerial coverage ordering, review queue, chip features.
No network. Synthetic inputs are test-only and are not evidence."""
import datetime as dt, importlib.util, json, pathlib, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
for sub in ("collector", "scripts"):
    sys.path.insert(0, str(ROOT / sub))
import residential_classifier as rc, aerial_coverage as ac, roof_score_v2 as v2, build_review_queue as rq
import weak_label_model as wl, roof_chip_features as cf
import numpy as np
from PIL import Image

NOW = dt.datetime(2026, 10, 23, tzinfo=dt.timezone.utc)
CTX = {"building_value": {}, "year_built": {}, "storms": {}, "storm_zips": set(), "reroof_year": {}, "aerial": {}, "chips": {}}
def ctx(**kw): return {**CTX, **kw}
def rec(pin="1", yb=1996, cls="SINGLE_FAMILY", verified=True, **kw):
    return {"county_pin": pin, "year_built": yb, "residential_class": cls, "single_family_verified": verified,
            "residential_likelihood": 0.97 if verified else 0.55, "zip": "55123", **kw}

class Classifier(unittest.TestCase):
    F = [{"name": "OBJECTID"}, {"name": "COUNTY_PIN"}, {"name": "USECLASS1"}, {"name": "DWELL_TYPE"},
         {"name": "NUM_UNITS"}, {"name": "OWNER_NAME"}, {"name": "YEAR_BUILT"}]
    def test_field_choice_skips_identity_and_owner(self):
        self.assertEqual(rc.choose_use_fields(self.F), ["USECLASS1", "DWELL_TYPE", "NUM_UNITS"])
    def test_single_family_only_when_source_says_so(self):
        u = rc.choose_use_fields(self.F)
        self.assertTrue(rc.classify({"DWELL_TYPE": "Single Family"}, u)["single_family_verified"])
        self.assertFalse(rc.classify({"USECLASS1": "RESIDENTIAL", "NUM_UNITS": 1}, u)["single_family_verified"])
        self.assertFalse(rc.classify({}, u)["single_family_verified"])
    def test_townhome_and_row_house_not_nonresidential(self):
        u = rc.choose_use_fields(self.F)
        self.assertEqual(rc.classify({"DWELL_TYPE": "ROW HOUSE"}, u)["residential_class"], "TOWNHOME")
    def test_commercial_excluded_and_likelihood_zero(self):
        c = rc.classify({"USECLASS1": "Commercial"}, ["USECLASS1"])
        self.assertTrue(c["non_residential_verified"]); self.assertEqual(c["residential_likelihood"], 0.0)
    def test_schema_cached_and_warns_when_no_use_field(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "s.json"; calls = []
            def fetch(_): calls.append(1); return [{"name": "OBJECTID"}, {"name": "COUNTY_PIN"}]
            s = rc.load_or_discover(p, fetch=fetch, now=NOW)
            self.assertEqual(s["use_fields"], []); self.assertIn("No use-type field", s["warning"])
            rc.load_or_discover(p, fetch=fetch, now=NOW + dt.timedelta(days=1))
            self.assertEqual(len(calls), 1)
            rc.load_or_discover(p, fetch=fetch, now=NOW + dt.timedelta(days=40))
            self.assertEqual(len(calls), 2)

class Scoring(unittest.TestCase):
    def s(self, r, c=CTX): return v2.score_parcel(r, c, NOW)
    def test_older_roof_ranks_above_newer(self):
        self.assertGreater(self.s(rec(yb=1996))["prospecting_priority"], self.s(rec(yb=2018))["prospecting_priority"])
    def test_verified_reroof_resets_age(self):
        old = self.s(rec(yb=1996)); new = self.s(rec(yb=1996), ctx(reroof_year={"1": 2024}))
        self.assertLess(new["prospecting_priority"], old["prospecting_priority"] / 2)
        self.assertEqual(new["factors"]["age_basis"], "VERIFIED_REROOF_PERMIT")
    def test_no_permit_is_flagged_unknown_not_original_roof(self):
        self.assertIn("ROOF_MAY_HAVE_BEEN_REPLACED_UNDETECTED", self.s(rec())["flags"])
    def test_nonresidential_excluded(self):
        x = self.s(rec(cls="NONRESIDENTIAL", verified=False), CTX)
        self.assertIsNone(x["prospecting_priority"])
    def test_never_claims_damage(self):
        x = self.s(rec())
        self.assertTrue(x["not_a_damage_score"]); self.assertEqual(x["condition_claim"], "NONE")
    def storm(self, date, hail=1.9):
        return ctx(storm_zips={"55123"}, storms={"55123": [{"event_id": "e", "date": date, "hail_inches": hail, "wind_mph": None}]})
    def test_storm_after_roof_raises_priority(self):
        self.assertGreater(self.s(rec(), self.storm("2025-06-01"))["prospecting_priority"], self.s(rec())["prospecting_priority"])
    def test_storm_before_roof_was_installed_ignored(self):
        c = ctx(**{**self.storm("2023-06-01"), "reroof_year": {"1": 2024}})
        self.assertEqual(self.s(rec(), c)["factors"]["storm_mult"], 1.0)
    def test_storm_boost_capped(self):
        ev = [{"event_id": str(i), "date": "2026-05-01", "hail_inches": 2.5, "wind_mph": 70} for i in range(10)]
        c = ctx(storm_zips={"55123"}, storms={"55123": ev})
        self.assertLessEqual(self.s(rec(), c)["factors"]["storm_mult"], 1.6001)
    def test_uncovered_zip_flagged_neutral(self):
        x = self.s(rec()); self.assertEqual(x["factors"]["storm_mult"], 1.0); self.assertIn("STORM_DATA_NOT_COVERING_THIS_ZIP", x["flags"])
    def test_unverified_class_discounted(self):
        self.assertLess(self.s(rec(cls="UNKNOWN", verified=False))["prospecting_priority"], self.s(rec())["prospecting_priority"])
    def test_chip_flags_move_priority_modestly_and_flag_review(self):
        base = self.s(rec())["prospecting_priority"]
        ch = self.s(rec(), ctx(chips={"1": {"possible_roof_change": True}}))
        self.assertLess(ch["prospecting_priority"], base); self.assertIn("POSSIBLE_ROOF_CHANGE_REVIEW", ch["flags"])
        self.assertGreater(self.s(rec(), ctx(chips={"1": {"possible_tarp": True}}))["prospecting_priority"], base)
    def test_confidence_rises_with_evidence(self):
        lo = self.s(rec(yb=0, cls="UNKNOWN", verified=False))["confidence"]
        hi = self.s(rec(), ctx(storm_zips={"55123"}, building_value={"1": 400000}, aerial={"1": {"status": "REMOTE_IMAGE_VERIFIED"}}))["confidence"]
        self.assertGreater(hi, lo)
    def test_priorities_not_clipped_into_ties(self):
        rs = [self.s(rec(pin=str(y), yb=y)) for y in range(1975, 2020)]
        self.assertGreater(len({r["prospecting_priority"] for r in rs}), 25)
    def test_tiers(self):
        rs = v2.assign_tiers([self.s(rec(pin=str(y), yb=y)) for y in range(1975, 2015)])
        t = [r["tier"] for r in sorted(rs, key=lambda r: r["rank"])]
        self.assertEqual(t[:4], ["A"] * 4); self.assertEqual(t[-1], "C")

class Aerial(unittest.TestCase):
    def test_order_prioritizes_verified_sf_skips_nonres_and_no_geometry(self):
        recs = [rec("a", verified=False, bbox_4326=[0, 0, 1, 1], residential_likelihood=.6),
                rec("b", bbox_4326=[0, 0, 1, 1]),
                rec("c", cls="NONRESIDENTIAL", verified=False, bbox_4326=[0, 0, 1, 1], non_residential_verified=True),
                rec("d")]
        self.assertEqual(ac.order(recs, {}, NOW), ["b", "a"])
    def test_stale_after_missing(self):
        recs = [rec("a", bbox_4326=[0, 0, 1, 1]), rec("b", bbox_4326=[0, 0, 1, 1])]
        led = {"a": {"checked_at_utc": (NOW - dt.timedelta(days=400)).isoformat()},
               "b": {"checked_at_utc": (NOW - dt.timedelta(days=5)).isoformat()}}
        self.assertEqual(ac.order(recs, led, NOW), ["a"])
    def test_probe_both_vintages_and_failure(self):
        r = rec("a", bbox_4326=[-93.2, 44.8, -93.19, 44.81])
        ok = lambda link: b"\xff\xd8\xff" + b"x" * 400 + b"\xff\xd9"
        _, e = ac.probe(r, True, None, fetcher=ok)
        self.assertEqual(set(e["layers"]), {"met25", "dak23"}); self.assertFalse(e["locally_downloaded"])
        self.assertFalse(e["resale_or_redistribution_rights_verified"])
        def bad(link): raise ValueError("down")
        _, e2 = ac.probe(r, False, None, fetcher=bad)
        self.assertEqual(e2["status"], "NOT_VERIFIED")
    def test_bbox_fallback_from_center(self):
        self.assertEqual(len(ac.bbox_of({"center_lat": 44.8, "center_lon": -93.1})), 4)
        self.assertIsNone(ac.bbox_of({}))

class Queue(unittest.TestCase):
    def test_uncertain_high_priority_first_and_prefilled_hash(self):
        scores = {"records": [
            {"county_pin": "a", "prospecting_priority": 60, "confidence": .9, "tier": "A", "flags": []},
            {"county_pin": "b", "prospecting_priority": 58, "confidence": .1, "tier": "A", "flags": ["X"]},
            {"county_pin": "c", "prospecting_priority": 90, "confidence": .5, "tier": "C", "flags": []}]}
        led = {"b": {"preferred_layer": "met25", "bbox_4326": [0, 0, 1, 1], "layers": {"met25": {"sha256": "f" * 64}}}}
        rows = rq.build(scores, led, {}, 10, lambda b, l: f"https://imageserver.gisdata.mn.gov/{l}")
        self.assertEqual([r["county_pin"] for r in rows], ["b", "a"])
        self.assertEqual(rows[0]["image_sha256"], "f" * 64); self.assertEqual(rows[0]["view"], "AERIAL")
        self.assertEqual(rows[0]["reviewer_id"], "")

class WeakLabels(unittest.TestCase):
    def test_refuses_thin_data(self):
        self.assertFalse(wl.train([[0.5, 1, 1, 10]] * 40, [1] * 20 + [0] * 20)["trained"])
    def test_rows_use_pre_permit_features_only(self):
        r = rec("a", yb=1990); seen = {}
        def fake(rr, c, now=None, use_permits=True): seen.update(now=now, use=use_permits); return v2.score_parcel(rr, c, now, use_permits)
        wl.build_rows([r], CTX, {"a": 2020}, {"a"}, fake)
        self.assertEqual(seen["now"].year, 2019); self.assertFalse(seen["use"])

class Chips(unittest.TestCase):
    def img(self, d, name, color, noise=0.0, seed=0):
        a = np.full((233, 300, 3), color, dtype=np.float32)
        a += np.random.default_rng(seed).normal(0, noise, a.shape)
        Image.fromarray(np.clip(a, 0, 255).astype("uint8")).save(d / name)
    def test_tarp_and_change(self):
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            self.img(d, "tarp.jpg", (30, 60, 200)); self.img(d, "gray.jpg", (110, 105, 100), 12, 1)
            self.img(d, "gray2.jpg", (125, 120, 116), 12, 1)   # same texture, brighter flight
            self.img(d, "other.jpg", (110, 105, 100), 40, 9)   # different texture
            self.assertTrue(cf.features_for(d / "tarp.jpg")["possible_tarp"])
            self.assertFalse(cf.features_for(d / "gray.jpg", d / "gray2.jpg")["possible_roof_change"])
            self.assertTrue(cf.features_for(d / "gray.jpg", d / "other.jpg")["possible_roof_change"])
            self.assertEqual(cf.features_for(d / "gray.jpg")["condition_claim"], "NONE")
if __name__ == "__main__": unittest.main()
