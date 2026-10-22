import sys
import pathlib
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"collector"))
from discover_outward_rings import merge_cumulative_rings

def parcel(i):
 return {"parcel_objectid":str(i),"county_pin":str(1000000+i),"address":f"{i} Source Ave, Eagan, MN",
 "ring":1,"distance_from_seed_center_m":350+i,
 "verification_status":"OFFICIAL_GIS_SOURCE_CANDIDATE","evidence_sha256":"b"*64}

class CumulativeGISDiscoveryTests(unittest.TestCase):
 def test_larger_scan_cannot_erase_earlier_official_records(self):
  previous=[parcel(i) for i in range(432)]
  scan=[parcel(i) for i in list(range(100,367))+list(range(432,533))]
  merged,added,history=merge_cumulative_rings(previous,scan)
  self.assertEqual(history,432)
  self.assertEqual(added,101)
  self.assertEqual(len(merged),533)
  self.assertEqual(len({x["county_pin"] for x in merged}),533)
  self.assertEqual(sum(x["observed_in_latest_geographic_query"] for x in merged),len(scan))
  self.assertTrue(merged[0]["evidence_sha256"]=="b"*64)
 def test_updated_same_pin_replaces_older_source_no_extra_parcel(self):
  old=parcel(1);fresh={**parcel(1),"address":"1 Officially Updated Street, Eagan, MN"}
  merged,added,history=merge_cumulative_rings([old],[fresh])
  self.assertEqual(len(merged),1);self.assertEqual(added,0)
  self.assertEqual(merged[0]["address"],fresh["address"])
 def test_conflicting_pin_to_object_id_fails_closed(self):
  old=parcel(1);bad={**parcel(2),"county_pin":old["county_pin"]}
  with self.assertRaisesRegex(ValueError,"Contradictory newly fetched"):
   merge_cumulative_rings([old],[bad])

if __name__=="__main__":unittest.main()
