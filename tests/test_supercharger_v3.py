"""Regression tests; synthetic records, no production or network access."""
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
for sub in ("scripts", "collector"):
    sys.path.insert(0, str(ROOT / sub))
import aerial_coverage as ac
import export_mindex_leads as mindex
import export_outreach_list as eo
import pipeline_io as io
import preflight
import roof_score_v2 as score

NOW = dt.datetime(2026, 10, 23, tzinfo=dt.timezone.utc)


class Reliability(unittest.TestCase):
    def test_mindex_export_honors_new_opt_out_with_stale_scores(self):
        cards = [{"county_pin": "p", "mindex": {"prospecting_priority": 70}},
                 {"county_pin": "q", "mindex": {"prospecting_priority": 60}}]
        self.assertEqual([r["county_pin"] for r in mindex.rows_for(cards, {"p"})], ["q"])

    def test_bad_calendar_dates_ignored(self):
        for value in ("2026-02-30", "2026-13-01", None, "bad"):
            self.assertIsNone(score._date(value))
        self.assertEqual(score._date("2024-02-29"), dt.date(2024, 2, 29))

    def test_failed_naive_future_checks_retry(self):
        recs = [{"county_pin": "p", "bbox_4326": [0, 0, 1, 1]}]
        for entry in (
            {"checked_at_utc": NOW.isoformat(), "status": "NOT_VERIFIED"},
            {"checked_at_utc": "2026-10-23", "status": "REMOTE_IMAGE_VERIFIED"},
            {"checked_at_utc": "2027-10-23T00:00:00+00:00", "status": "REMOTE_IMAGE_VERIFIED"},
            {"checked_at_utc": None},
        ):
            self.assertEqual(ac.order(recs, {"p": entry}, NOW), ["p"])
        self.assertEqual(ac.order(recs, {"p": {"checked_at_utc": NOW.isoformat(),
                          "status": "REMOTE_IMAGE_VERIFIED"}}, NOW), [])

    def test_strict_suppression(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "suppression.json"
            self.assertEqual(io.load_suppression(p), set())
            for payload in ('{', '{}', '{"pins":"p"}', '{"pins":[null]}'):
                p.write_text(payload)
                with self.assertRaises(ValueError): io.load_suppression(p)
            io.atomic_json(p, {"pins": ["p"]})
            self.assertEqual(io.load_suppression(p), {"p"})

    def test_atomic_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "data.json"
            io.atomic_json(p, {"old": True})
            with patch.object(io.os, "replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError): io.atomic_json(p, {"new": True})
            self.assertEqual(json.loads(p.read_text()), {"old": True})
            self.assertEqual(list(Path(d).iterdir()), [p])

    def test_export_validates_limits(self):
        for tiers, top in (({"A"}, -1), ({"X"}, 10), (set(), 10)):
            with self.assertRaises(ValueError): eo.select({"records": []}, set(), tiers, top)

    def test_preflight_missing_base_and_corrupt_data(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(preflight.inspect(root, False)["status"], "BLOCKED")
            for file in preflight.BASE_FILES:
                p = root / file; p.parent.mkdir(parents=True, exist_ok=True); p.touch()
            self.assertEqual(preflight.inspect(root, False)["status"], "OFFLINE_CHECKS_PASSED")
            io.atomic_json(root / "evidence/data/outreach_suppression.json", {"pins": "wrong"})
            self.assertEqual(preflight.inspect(root, False)["status"], "BLOCKED")

    def test_scoring_stops_on_corrupt_suppression(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "outreach_suppression.json"; p.write_text('{"pins":"bad"}')
            with patch.object(score, "DATA", Path(d)):
                with self.assertRaises(ValueError): score.build_context()

if __name__ == "__main__": unittest.main()
