import csv
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"collector"))
from validate_imagery_view_sources import build

class VerifiedImageryLinksTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir=pathlib.Path(self.temp.name)
        with (self.dir/"kingswood_parcel_candidates.csv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=["parcel_objectid","county_pin","address"])
            writer.writeheader()
            for i in range(60):
                writer.writerow({"parcel_objectid":str(44001+i),"county_pin":str(104200100000+i),"address":str(1400+i)+" Kings Wood Lane"})
    def test_source_hash_does_not_become_downloaded_or_inspected(self):
        record={"parcel_objectid":"44001","county_pin":"104200100000",
          "imagery":"GOVERNMENT_REMOTE_JPEG_VERIFIED",
          "imagery_source_url":"https://imageserver.gisdata.mn.gov/cgi-bin/wmsll?SERVICE=WMS&LAYERS=met25",
          "imagery_sha256":"a"*64,"imagery_verified_bytes":1500,"imagery_year":2025,
          "imagery_layer":"met25","last_checked_utc":"2026-10-19T06:00:00Z"}
        (self.dir/"fast_validation_report.json").write_text(json.dumps({"run_utc":"2026-10-19T06:00:00Z","records":[record]}))
        result=build(self.dir)
        self.assertEqual(result["original_parcels"],60)
        self.assertEqual(result["remote_jpeg_last_verified"],1)
        self.assertEqual(result["local_image_files_published"],0)
        self.assertFalse(result["source_availability_complete"])
        self.assertFalse(result["records"][0]["locally_downloaded"])
        self.assertFalse(result["records"][0]["roof_condition_verified"])
    def test_mismatched_pin_and_non_government_urls_never_pass(self):
        records=[{"parcel_objectid":"44001","county_pin":"WRONG","imagery":"GOVERNMENT_REMOTE_JPEG_VERIFIED",
          "imagery_source_url":"https://imageserver.gisdata.mn.gov/cgi-bin/wmsll?foo=bar",
          "imagery_sha256":"a"*64,"imagery_verified_bytes":800},
          {"parcel_objectid":"44002","county_pin":"104200100001","imagery":"GOVERNMENT_REMOTE_JPEG_VERIFIED",
          "imagery_source_url":"https://unknown.example/evil","imagery_sha256":"b"*64,
          "imagery_verified_bytes":800}]
        (self.dir/"fast_validation_report.json").write_text(json.dumps({"records":records}))
        result=build(self.dir)
        self.assertEqual(result["remote_jpeg_last_verified"],0)
        self.assertTrue(all(x["source_status"]=="SOURCE_NOT_VALIDATED" for x in result["records"]))
    def test_rejects_changed_original_inventory(self):
        (self.dir/"kingswood_parcel_candidates.csv").write_text("parcel_objectid,county_pin,address\n44001,1,one\n")
        with self.assertRaisesRegex(ValueError,"60 original"):build(self.dir)

if __name__=="__main__":
    unittest.main()
