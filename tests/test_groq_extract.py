import datetime as dt
import json
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"collector"))
import groq_extract as g

class MockTransport:
    def __init__(self,payload):
        self.payload=payload
        self.calls=[]
    def __call__(self,request,timeout=0):
        self.calls.append({"url":request.full_url,"timeout":timeout,
          "data":json.loads(request.data)})
        return self
    def __enter__(self):return self
    def __exit__(self,*_):return None
    def read(self,limit=None):
        return json.dumps({"choices":[{"message":{"content":self.payload}}]}).encode()

class TestGroqUpgrade(unittest.TestCase):
    def test_unverified_always_even_when_model_claims_verification(self):
        proposal=g.clean(json.dumps({"verified":True,"is_roof_permit":True,"confidence":.95,
          "permit_date":"2025-06-20"}))
        self.assertIs(proposal["verified"],False)
        self.assertEqual(proposal["status"],"UNVERIFIED_PROPOSAL")
    def test_bad_structure_and_dates_are_not_evidence(self):
        self.assertIsNone(g.clean("not json"))
        self.assertIsNone(g.clean("[]"))
        self.assertIsNone(g.clean("null"))
        self.assertIsNone(g.clean("{}")["permit_date"])
    def test_confidence_bounded_and_dangerous_values_not_promoted(self):
        self.assertEqual(g.clean('{"confidence":-2}')["confidence"],0)
        self.assertEqual(g.clean('{"confidence":10}')["confidence"],1)
        self.assertEqual(g.clean('{"confidence":"nan"}')["confidence"],0)
    def test_real_network_never_called_during_unit_test(self):
        fake=MockTransport('{"is_roof_permit":true,"permit_date":"2025-06-20","confidence":0.75}')
        out=g.run([{"ref":"municipal-2506-00458-BL","text":"Replace house shingles"}],
          key="fake-test-key",model="unit-test",opener=fake,pause=0)
        self.assertEqual(len(out),1)
        self.assertIs(out[0]["proposal"]["verified"],False)
        self.assertTrue(out[0]["human_and_original_issuer_review_required"])
        self.assertEqual(fake.calls[0]["url"],g.URL)
        self.assertLessEqual(len(fake.calls[0]["data"]["messages"][-1]["content"]),g.MAX_TEXT)
    def test_batches_above_limit_rejected_without_network(self):
        fake=MockTransport("{}")
        with self.assertRaises(ValueError):g.run([{"text":"x"}]*21,
          key="fake",model="unit-test",opener=fake,pause=0)
        self.assertEqual(len(fake.calls),0)
    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):g.run([{"ref":"a"}],
          key="fake",model="unit-test",opener=MockTransport("{}"),pause=0)

if __name__=="__main__": unittest.main()
