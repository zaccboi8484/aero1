import csv,importlib.util,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('backfill',ROOT/'collector/roof_permit_backfill.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class BackfillTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name)
  with (self.path/'kingswood_parcel_candidates.csv').open('w') as f:
   f.write('parcel_objectid,county_pin,address\n101,123456789012,"1402 Kings Wood Road, Eagan, MN"\n')
  (self.path/'roof_evidence_scores.json').write_text(json.dumps({'records':[{'county_pin':'123456789012','review':{'data_review_priority':80}}]}))
 def tearDown(self):self.tmp.cleanup()
 def sample(self,**overrides):
  row={'permit_number':'PERM-1','property_address':'1402 Kings Wood Road, Eagan, MN','permit_type':'Re-roof shingles',
   'permit_status':'Final','final_date':'2025-09-10','source_url':'https://eagan.onlama.com/record/1',
   'review_status':'REVIEWED','reviewer_id':'human-1','reviewed_at':'2026-10-15'}
  row.update(overrides)
  p=self.path/'official.csv'
  with p.open('w',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=row.keys());writer.writeheader();writer.writerow(row)
  return p
 def test_verified_recent_roof_lowers_priority(self):
  result=mod.build(self.path,self.sample())['records'][0]
  self.assertEqual(result['roofing_outreach_priority'],35)
  self.assertTrue(result['recent_roof_verified'])
 def test_missing_reviewer_does_not_lower(self):
  result=mod.build(self.path,self.sample(reviewer_id=''))['records'][0]
  self.assertEqual(result['roofing_outreach_priority'],80)
 def test_wrong_year_does_not_lower(self):
  result=mod.build(self.path,self.sample(final_date='2024-09-10'))['records'][0]
  self.assertEqual(result['roofing_outreach_priority'],80)
 def test_unmatched_address_rejected(self):
  result=mod.build(self.path,self.sample(property_address='9999 Fake St'))
  self.assertEqual(result['records'][0]['roofing_outreach_priority'],80)
 def test_no_csv_still_auditable(self):
  result=mod.build(self.path)
  self.assertFalse(result['municipal_export_connected'])
  self.assertEqual(result['records'][0]['search_status'],'NO_MATCH_FROM_AVAILABLE_EVIDENCE')
if __name__=='__main__':unittest.main()