#!/usr/bin/env python3
"""Offline tests: no synthetic records are emitted as evidence."""
import importlib.util,pathlib,tempfile,csv,json,hashlib
p=pathlib.Path(__file__).resolve().parents[1]/"collector/match_permits.py"
spec=importlib.util.spec_from_file_location("permits",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert m.address_key("1402 Kings Wood Road, Eagan, MN")==m.address_key("1402 KINGS WOOD RD")
parcel=[{"address":"1402 Kings Wood Road, Eagan, MN","county_pin":"SAMPLE-ONLY","parcel_objectid":"OFFLINE-TEST"}]
permit=[{"Permit Number":"TEST-1","Site Address":"1402 Kings Wood Rd","Permit Type":"Roofing","Status":"Issued","Issue Date":"2024-01-01"}]
matched=m.reconcile(parcel,permit,"offline-test.csv")
assert len(matched)==1
assert matched[0]["match_status"]=="EXACT_ADDRESS_PENDING_REVIEW"
assert matched[0]["verification_status"]=="UNVERIFIED"
assert matched[0]["inspection_claim"] is None
assert matched[0]["classification"]=="UNKNOWN"
unmatched=m.reconcile(parcel,[{"Permit Number":"TEST-2","Site Address":"9999 Different St"}],"offline-test.csv")
assert unmatched[0]["match_status"]=="UNMATCHED"
assert unmatched[0]["county_pin"] is None
assert len(m.reconcile(parcel,[],"offline-test.csv"))==0
print("Permit normalizer and non-fabrication rules PASSED")
