"""Certification pipeline tests use the actual committed Eagan evidence files.

These tests guard against false certification, contradictory parcel identities,
duplicate permits, forged results, wrong house/PIN joins, and unlicensed sources.
"""
import csv
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"collector"))
from certification_gap_pipeline import compile_gap_index, publish, safe_source

FILES=("kingswood_parcel_candidates.csv","municipal_permit_export_audit.json",
       "mn_address_validation.json","live_property_enrichment.json",
       "imagery_source_availability.json","fast_validation_report.json",
       "gatekeeper_release_truth.json")

class GapPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.d=pathlib.Path(self.temp.name)
        for name in FILES:
            shutil.copyfile(ROOT/"evidence/data"/name,self.d/name)
    def read(self,name):
        return json.loads((self.d/name).read_text(encoding="utf-8"))
    def put(self,name,data):
        (self.d/name).write_text(json.dumps(data),encoding="utf-8")

    def test_real_first_sixty_have_true_gaps_and_precise_permit_requests(self):
        summary,queue,rows=publish(self.d)
        self.assertEqual(summary["original_residential_parcels"],60)
        self.assertEqual(summary["export_report_matches_pending_document_review"],25)
        self.assertEqual(summary["properties_with_export_matches"],18)
        self.assertEqual(summary["priority_roof_2025_candidates"],1)
        self.assertEqual(summary["gis_address_matched"],56)
        self.assertEqual(summary["valuation_source_matched"],56)
        self.assertEqual(summary["assessment_year_proven"],0)
        self.assertEqual(summary["remote_wms_image_hashes"],60)
        self.assertEqual(summary["original_issuer_permit_documents_reviewed"],0)
        self.assertEqual(summary["human_reviewed_roof_conditions"],0)
        self.assertEqual(summary["certified_mindex_scores"],0)
        self.assertFalse(summary["release_certified"])
        self.assertEqual(summary["open_tasks_by_kind"]["ORIGINAL_ISSUER_PERMIT_DOCUMENT"],25)
        self.assertEqual(summary["open_tasks_by_kind"]["MUNICIPAL_FULL_PERMIT_HISTORY"],60)
        self.assertEqual(summary["open_tasks_by_kind"]["ADDRESS_GIS_RECONCILIATION"],4)
        self.assertEqual(summary["open_tasks_by_kind"]["OFFICIAL_ASSESSMENT_RECORD"],4)
        self.assertEqual(summary["open_tasks_by_kind"]["ASSESSMENT_YEAR_PROVENANCE"],60)
        self.assertEqual(summary["open_tasks_by_kind"]["PHYSICAL_ROOF_CONDITION_REVIEW"],60)
        self.assertEqual(summary["open_tasks_by_kind"]["EVIDENCE_SUPPORTED_MINDEX"],60)
        self.assertEqual(summary["task_count"],len(queue["tasks"]))
        self.assertEqual(len({x["task_id"] for x in queue["tasks"]}),summary["task_count"])
        self.assertEqual(len(rows),25)
        self.assertTrue(summary["public_eagan_portal_403_observed"])
        roof=[x for x in queue["tasks"] if x["source_record_id"]=="2506-00458-BL"]
        self.assertEqual(len(roof),1)
        self.assertEqual(roof[0]["parcel_objectid"],"44018")
        self.assertEqual(roof[0]["priority"],1)
        self.assertFalse(roof[0]["certification_approved"])
        self.assertFalse(any(x["completed"] for x in queue["tasks"]))
        self.assertEqual(len(list(csv.DictReader((self.d/"permit_issuer_review_queue.csv").open()))),25)

    def test_duplicate_or_conflicting_permit_cannot_be_certified(self):
        data=self.read("municipal_permit_export_audit.json")
        data["records"].append(dict(data["records"][0]))
        data["matched_permit_events"]+=1
        self.put("municipal_permit_export_audit.json",data)
        with self.assertRaisesRegex(ValueError,"duplicate city permit"):compile_gap_index(self.d)

    def test_contradictory_county_pin_is_rejected(self):
        data=self.read("mn_address_validation.json")
        data["records"][0]["county_pin"]="999999999999"
        self.put("mn_address_validation.json",data)
        with self.assertRaisesRegex(ValueError,"Contradictory address county PIN"):compile_gap_index(self.d)

    def test_missing_source_never_passes_as_zero(self):
        (self.d/"municipal_permit_export_audit.json").unlink()
        with self.assertRaisesRegex(ValueError,"Required evidence"):compile_gap_index(self.d)

    def test_original_60_cannot_expand_or_shrink_silently(self):
        p=self.d/"kingswood_parcel_candidates.csv"
        lines=p.read_text(encoding="utf-8").splitlines()
        p.write_text("\n".join(lines[:-1])+"\n",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"exactly 60"):compile_gap_index(self.d)

    def test_redirect_and_unlicensed_urls_fail_safe(self):
        self.assertFalse(safe_source("https://evil.example/eagan"))
        self.assertFalse(safe_source("http://eagan.onlama.com/Search.aspx"))
        self.assertFalse(safe_source("https://user:pass@eagan.onlama.com/Search.aspx"))
        self.assertTrue(safe_source("https://eagan.onlama.com/Search.aspx"))

if __name__=="__main__":
    unittest.main()
