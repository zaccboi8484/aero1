import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"collector"))
from repair_source_ledger import merge_reports

class RecoveryTests(unittest.TestCase):
 def test_restore_only_real_prior_source_rows_and_preserve_newer_checks(self):
  old={"records":[{"county_pin":"111","parcel_objectid":"1","last_checked_utc":"2026-10-01T00:00:00Z","parcel_validation":"OFFICIAL_PIN_CONFIRMED"},
    {"county_pin":"222","parcel_objectid":"2","last_checked_utc":"2026-10-01T00:00:00Z","imagery":"GOVERNMENT_REMOTE_JPEG_VERIFIED"}]}
  fresh={"run_utc":"2026-10-22T22:32:35Z","total_indexed":492,
   "records":[{"county_pin":"111","parcel_objectid":"1","last_checked_utc":"2026-10-22T00:00:00Z","parcel_validation":"GIS_NO_MATCH"},
              {"county_pin":"333","parcel_objectid":"3","last_checked_utc":"2026-10-22T00:00:00Z","parcel_validation":"OFFICIAL_PIN_CONFIRMED"}]}
  x=merge_reports(fresh,old)
  self.assertEqual(len(x["records"]),3)
  self.assertEqual({r["county_pin"]:r for r in x["records"]}["111"]["parcel_validation"],"GIS_NO_MATCH")
  self.assertEqual({r["county_pin"]:r for r in x["records"]}["222"]["imagery"],"GOVERNMENT_REMOTE_JPEG_VERIFIED")
  self.assertEqual(x["historical_source_recovery"]["recovered_observations"],1)
  self.assertEqual(x["run_utc"],fresh["run_utc"])
 def test_conflicting_identity_fails_closed(self):
  p={"records":[{"county_pin":"111","parcel_objectid":"A"}]}
  c={"records":[{"county_pin":"111","parcel_objectid":"B"}]}
  with self.assertRaisesRegex(ValueError,"Conflicting parcel identity"):merge_reports(c,p)
 def test_missing_reports_do_not_get_fabricated(self):
  with self.assertRaisesRegex(ValueError,"observation lists"):merge_reports({"records":[]},{})
if __name__=="__main__":unittest.main()
