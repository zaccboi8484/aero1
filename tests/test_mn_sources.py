"""Zero-credential source standards. Passing is not proof images or USPS have been fetched."""
import unittest,importlib.util,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/"collector"/(name+".py"))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
class GateKeeperSources(unittest.TestCase):
 def test_wms_layers_and_source(self):
  a=load("collect_mngeo_aerial")
  self.assertTrue(a.url([-93.2,44.8,-93.1,44.9],"met25").startswith("https://imageserver.gisdata.mn.gov/"))
  with self.assertRaises(ValueError):a.url([-93.2,44.8,-93.1,44.9],"untrusted")
 def test_address_normalization(self):
  a=load("validate_mn_addresses")
  self.assertEqual(a.norm("1402 Kings Wood Road"),a.norm("1402 kings wood rd"))
 def test_gatekeeper_pulse_has_human_approval(self):
  a=load("gatekeeper_pulse")
  self.assertIn("municipal_permits",a.RECOMMEND)
  self.assertIn("mngeo_aerial",a.SOURCES)
if __name__=="__main__":unittest.main()
