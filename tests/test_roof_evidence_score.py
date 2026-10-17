"""Safety and useful-scoring tests for GateKeeper roof evidence rubric."""
import importlib.util,pathlib,unittest
p=pathlib.Path(__file__).resolve().parents[1]/"collector"/"roof_evidence_score.py"
spec=importlib.util.spec_from_file_location("roof",p);roof=importlib.util.module_from_spec(spec);spec.loader.exec_module(roof)
SHA="a"*64
BASE={"source_type":"USER_UPLOADED","consent_to_process":True,"source_url":"https://example.org/private-upload/roof.jpg",
 "image_sha256":SHA,"capture_date":"2025-04-18T12:00:00+00:00","roof_region_reviewed":True,
 "reviewer_id":"qualified-reviewer-123","reviewed_at":"2026-10-17T12:00:00+00:00",
 "view":"CLOSE_RANGE","indicators":["missing_shingles"],"lookalikes":[]}
class TestRoof(unittest.TestCase):
 def test_missing_review_rejects_score(self):
  x={**BASE,"reviewer_id":None}
  self.assertIsNone(roof.score_roof(x,{SHA})["roof_condition_score"])
 def test_google_analysis_forbidden(self):
  x={**BASE,"source_url":"https://maps.googleapis.com/satellite","source_type":"MN_GOV"}
  self.assertIsNone(roof.score_roof(x,{SHA})["roof_condition_score"])
 def test_unproven_image_hash_rejected(self):
  self.assertIsNone(roof.score_roof(BASE,set())["roof_condition_score"])
 def test_aerial_cannot_certify_hail_damage(self):
  x={**BASE,"view":"AERIAL","indicators":["random_pattern_hail_bruises"]}
  self.assertIsNone(roof.score_roof(x,{SHA})["roof_condition_score"])
 def test_government_orthophoto_cannot_pretend_closeup(self):
  x={**BASE,"source_type":"MN_GOV","source_url":"https://imageserver.gisdata.mn.gov/cgi-bin/wmsll"}
  self.assertIn("ORTHOPHOTO_CANNOT_BE_CLOSE_RANGE",roof.score_roof(x,{SHA})["issues"])
 def test_verified_photo_allows_condition_score(self):
  x=roof.score_roof(BASE,{SHA})
  self.assertEqual(x["status"],"REVIEWED_ROOF_EVIDENCE_SCORE")
  self.assertEqual(x["roof_condition_score"],28)
 def test_lookalikes_lower_score(self):
  x=roof.score_roof({**BASE,"lookalikes":["blistering"]},{SHA})
  self.assertLess(x["roof_condition_score"],28)
 def test_priorty_no_damage_claim(self):
  p=roof.priority({"year_built":"1994"},{},False,False,False)
  self.assertEqual(p["data_review_priority"],100)
  self.assertTrue(p["not_a_damage_score"])
if __name__=="__main__":unittest.main()
