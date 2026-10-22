import csv,json,pathlib,tempfile,unittest,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"collector"))
from merge_ring_history import OFFICIAL,merge

def row(pin,oid,dist=400):
 return {"county_pin":pin,"parcel_objectid":oid,"center_lat":44.8,"center_lon":-93.1,
 "address":oid+" Kings Wood Rd, Eagan MN","ring":1,
 "distance_from_seed_center_m":dist,"verification_status":"OFFICIAL_GIS_SOURCE_CANDIDATE",
 "source_record_url":OFFICIAL+"?f=json&where=OBJECTID%3D"+oid}
def snapshot(rows):
 return {"source":OFFICIAL,"seed_count":60,"source_query_completed":True,"errors":[],
  "generated_at_utc":"2026-10-22T11:00:00Z","candidate_count":len(rows),"ring_candidates":rows}
class RingHistory(unittest.TestCase):
 def test_growth_never_deletes_old_official_observations(self):
  older=snapshot([row("101000000001","44061"),row("101000000002","44062")])
  fresh=snapshot([row("101000000002","44062"),row("101000000003","44063")])
  result=merge(fresh,[("commit-observation",older)])
  self.assertEqual(result["candidate_count"],3)
  self.assertEqual(result["historical_source_reconciliation"]["historical_official_records_retained"],1)
  self.assertEqual(len([p for p in result["ring_candidates"] if p["observed_in_current_source_query"]]),2)
  self.assertEqual(next(p for p in result["ring_candidates"] if p["county_pin"]=="101000000001")["historical_source_commit"],"commit-observation")
 def test_conflicting_pin_or_id_halts(self):
  old=snapshot([row("101000000001","44061")])
  fresh=snapshot([row("101000000001","44099")])
  with self.assertRaisesRegex(ValueError,"Conflicting official GIS PIN"):merge(fresh,[("prior",old)])
 def test_failure_cannot_appear_as_complete_discovery(self):
  broken=snapshot([row("101000000002","44062")])
  broken["source_query_completed"]=False
  with self.assertRaisesRegex(ValueError,"incomplete"):merge(broken,[])
 def test_untrusted_public_records_cannot_enter_registry(self):
  fake=snapshot([row("101000000002","44062")])
  fake["ring_candidates"][0]["source_record_url"]="https://other.example/claim"
  with self.assertRaisesRegex(ValueError,"provenance"):merge(fake,[])
if __name__=="__main__":unittest.main()
