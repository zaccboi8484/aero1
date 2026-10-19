import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"collector"))
from source_health_public import summarise

class LiveSourceHealthTests(unittest.TestCase):
    def test_real_source_observation_without_claiming_review(self):
        with tempfile.TemporaryDirectory() as temp:
            path=pathlib.Path(temp)
            (path/"fast_validation_report.json").write_text(json.dumps({
                "run_utc":"2026-10-19T06:00:00+00:00",
                "total_indexed":417,"batch_attempted":8,
                "municipal_permit_source":{"status":"PUBLIC_SOURCE_UNAVAILABLE","error":"HTTP 403: Forbidden"},
                "records":[{"parcel_validation":"OFFICIAL_PIN_CONFIRMED","imagery":"GOVERNMENT_REMOTE_JPEG_VERIFIED"},
                  {"parcel_validation":"OFFICIAL_PIN_CONFIRMED","imagery":"NO_BOUNDING_BOX_YET"}]
            }))
            (path/"municipal_permit_export_audit.json").write_text(json.dumps({
                "records":[{"permit_number":"2506-00458-BL"},{"permit_number":"2505-00100-BL"}]
            }))
            (path/"gatekeeper_release_truth.json").write_text('{"release_certified":false}')
            result=summarise(path)
            self.assertEqual(result["format"],"GATEKEEPER_SOURCE_HEARTBEAT_V1")
            self.assertEqual(result["source_report_run_utc"],"2026-10-19T06:00:00+00:00")
            self.assertEqual(result["counts"]["indexed_parcels"],417)
            self.assertEqual(result["counts"]["parcels_checked_last_run"],8)
            self.assertEqual(result["counts"]["municipal_report_matches"],2)
            self.assertEqual(result["counts"]["government_jpeg_response_records"],1)
            self.assertTrue(result["municipal_portal_access_blocked"])
            self.assertEqual(result["counts"]["permit_documents_reviewed"],0)
            self.assertFalse(result["release_certified"])
    def test_missing_report_cannot_pass_as_fresh(self):
        with tempfile.TemporaryDirectory() as temp:
            result=summarise(pathlib.Path(temp))
            self.assertFalse(result["source_data_present"])
            self.assertIsNone(result["source_report_run_utc"])
            self.assertEqual(result["municipal_portal_status"],"NOT_CHECKED")
            self.assertFalse(result["release_certified"])

if __name__=="__main__":
    unittest.main()
