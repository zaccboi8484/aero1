"""AeroLeadAI crawler must process unseen GIS parcels before rechecking old 60."""
import sys
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"collector"))
from frequent_source_validation import select_research_batch

def record(i):
 return {"parcel_objectid":str(i),"county_pin":f"MN{i:07d}","address":f"{i} Official Street"}

class RealCrawlBatchTests(unittest.TestCase):
 def test_new_ring_parcels_are_checked_before_rechecking_existing(self):
  rows=[record(i) for i in range(492)]
  saved={x["county_pin"]:{"parcel_validation":"OFFICIAL_PIN_CONFIRMED"} for x in rows[:417]}
  chosen,cursor,unseen=select_research_batch(rows,saved,0,24)
  self.assertEqual(unseen,75)
  self.assertEqual(len(chosen),24)
  self.assertTrue(all(p["county_pin"] not in saved for p in chosen))
  for p in chosen:saved[p["county_pin"]]={"parcel_validation":"OFFICIAL_PIN_CONFIRMED"}
  nextbatch,cursor,remaining=select_research_batch(rows,saved,cursor,24)
  self.assertEqual(remaining,51)
  self.assertTrue(all(p["county_pin"] not in saved for p in nextbatch))
 def test_batches_have_no_duplicate_pins_and_rotate_after_backlog(self):
  rows=[record(i) for i in range(61)]
  saved={r["county_pin"]:r for r in rows}
  picked,cursor,unseen=select_research_batch(rows,saved,0,24)
  self.assertEqual(unseen,0)
  self.assertEqual(len(picked),24)
  self.assertEqual(len({p["county_pin"] for p in picked}),24)
  self.assertEqual(cursor,24)
  nextpicked,cursor,_=select_research_batch(rows,saved,cursor,24)
  self.assertEqual(nextpicked[0]["county_pin"],rows[24]["county_pin"])
 def test_incomplete_last_batch_does_not_overrun(self):
  rows=[record(i) for i in range(6)]
  chosen,cursor,unseen=select_research_batch(rows,{},0,24)
  self.assertEqual(unseen,6)
  self.assertEqual(len(chosen),6)
  self.assertEqual({x["county_pin"] for x in chosen},{x["county_pin"] for x in rows})
 def test_old_60_not_special_cap(self):
  rows=[record(i) for i in range(1200)]
  batch,_,unseen=select_research_batch(rows,{},0,24)
  self.assertEqual(unseen,1200)
  self.assertEqual(len(batch),24)

if __name__=="__main__":unittest.main()
